#!/usr/bin/env python
# encoding: utf-8

import os
import re
import sys
import time
import copy
import unittest
import requests
from subprocess import Popen, PIPE

sys.path.append(os.path.expandvars('$PWD'))

from ztest import Lexer, Cases, ContextTestCase

request_match = re.compile(
    r'^\s*(?P<method>\w+) (?P<uri>\S+) ?(?P<version>\S+)?(\n|$)'
    r'(?P<headers>(^.+(\n|$))+)?'
    r'(\n(?P<body>([\s\S])+))?', re.M
).match

test_directory = 't/nginx'
openresty_root = '/usr/local/openresty/nginx'
nginx_log_path = 't/nginx/servroot/logs/error.log'
nginx_api = '127.0.0.1:1984'
nginx_template = '''
worker_processes  1;

error_log  logs/error.log  info;
pid        logs/nginx.pid;

events {
    worker_connections  1024;
}

http {
    include       mime.types;
    default_type  application/octet-stream;

    sendfile        on;
    keepalive_timeout  65;

    server {
        listen       1984;
        server_name  localhost;

%(config)s
    }
}
'''


def shell(command):
    process = Popen(
        args=command,
        stdout=PIPE,
        shell=True
    )

    return process.communicate()[0]


def gather_files(test_dir):
    if os.path.isfile(test_dir):
        return [test_dir] if test_dir.endswith('zt') else []

    test_files = []
    for d, _, files in os.walk(test_dir):
        test_files.extend(os.path.join(d, f) for f in
                          filter(lambda f: f.endswith('zt'), files))

    return test_files


def file_size(f):
    with open(f, 'r') as fd:
        fd.seek(0, os.SEEK_END)
        return fd.tell()


def seek_read(f, pos):
    with open(f, 'r') as fd:
        fd.seek(pos, os.SEEK_SET)
        return fd.read()


def get_nginx_log(fn):
    def wrapper(*args, **kwargs):
        start = file_size(nginx_log_path)
        self = args[0]
        r = fn(*args, **kwargs)
        self.error_log += seek_read(nginx_log_path, start)
        return r
    return wrapper


def add_test_case(zt, suite, cases, env):
    for case in cases:
        if case.name is None:
            case.name = ''
        case.name = re.sub(r'[^.\w]+', '_', case.name)
        suite.addTest(
            ContextTestCase.addContext(
                type('%s<%s:%s>' % (case.name, zt, case.lineno),
                     (TestNginx,), {}), ctx=Ctx(case, env)))


def get_headers(text):
    if text is None:
        return
    lines = text.split('\n')
    headers = {}
    for line in lines:
        line = line.strip()
        if line:
            k, v = line.split(':', 1)
            headers[k.strip()] = v and v.strip() or ''

    return headers


class Ctx(object):
    def __init__(self, case, env):
        self.case = case
        self.env = env


class TestNginx(ContextTestCase):
    common_items = ['config', 'setup', 'teardown']
    assert_items = ['response', 'response_body', 'response_headers',
                    'status_code', 'no_error_log', 'error_log']
    leading_items = ['setenv', 'request', 'more_headers', 'request_body']
    block_items = leading_items + assert_items
    items = common_items + block_items

    def setUp(self):
        self.setup_ = None
        self.teardown_ = None
        self.skip = False
        self.error_log = ''

        if self.__class__.__name__ == 'TestNginx':
            self.skip = True
            return

        if self.ctx is None or not self.ctx.case:
            raise Exception('no test case found')

        self.name = self.ctx.case.name
        self.items = self.ctx.case.items
        if isinstance(self.ctx.env, dict):
            self.env = self.ctx.env
        else:
            self.env = {}
        self.env['_'] = self

        self.prepare()

        if self.setup_:
            self.setup_()

    def tearDown(self):
        if self.teardown_:
            self.teardown_()

    def config(self, data):
        servroot = os.path.join(os.path.expandvars('$PWD'), test_directory,
                                'servroot')
        logspath = os.path.join(servroot, 'logs')
        confpath = os.path.join(servroot, 'conf')
        nginxbin = os.path.join(openresty_root, 'sbin', 'nginx')

        shell('mkdir -p %s' % logspath)
        shell('cp -r %s/conf %s' % (openresty_root, servroot))

        conf = os.path.join(confpath, 'nginx.conf')
        open(conf, 'w+').write(nginx_template % {'config': data})

        pid = os.path.join(logspath, 'nginx.pid')
        if os.path.isfile(pid):
            shell('kill -HUP `cat %s`' % pid)
            time.sleep(.2)
        else:
            shell('%s -p %s -c %s' % (nginxbin, servroot, 'conf/nginx.conf'))

    def setup(self, code):
        self.setup_ = lambda: self._exec(code)

    def teardown(self, code):
        self.teardown_ = lambda: self._exec(code)

    def setenv(self, code):
        self._exec(code)

    def prepare(self):
        for idx, item in enumerate(self.items):
            if item.name in TestNginx.common_items:
                if 'eval' in item.option:
                    item.value = eval(item.value, None, self.env)
                getattr(self, item.name)(item.value)
            if item.name in TestNginx.leading_items:
                break
        self.items = self.items[idx:]

    def _blocks(self):
        block = {}
        for item in self.items:
            if 'eval' in item.option:
                item.value = eval(item.value, None, self.env)
            if item.name in TestNginx.leading_items:
                if item.name in block:
                    yield block
                    block = {}
                block[item.name] = item
            elif item.name in TestNginx.assert_items:
                if block:
                    yield block
                yield item

    def _exec(self, code):
        exec(code, None, self.env)

    @get_nginx_log
    def do_request(self, block):
        request = block['request']
        if 'exec' in request.option:
            return self._exec(request.value)

        m = request_match(request.value)
        assert m, 'invalid request block: ' + request.value

        headers, body = m.group('headers'), m.group('body')
        if 'more_headers' in block:
            if headers is None:
                headers = block['more_headers'].value
            else:
                headers += '\n' + block['more_headers'].value
        if 'request_body' in block:
            if body is None:
                body = block['request_body'].value
            else:
                body += block['request_body'].value

        headers = get_headers(headers)
        method, uri = m.group('method'), m.group('uri')
        if uri.startswith('/'):
            uri = 'http://%s%s' % (nginx_api, uri)
        elif not re.match(r'https?://'):
            uri = 'http://%s/%s' % (nginx_api, uri)
        return getattr(requests,
                       method.lower())(uri, headers=headers, data=body)

    def do_requests(self, block):
        r = []
        for req in block['request'].value:
            if not isinstance(req, str):
                raise Exception('unexpected request type: ' + type(req))
            _block = copy.deepcopy(block)
            _block['request'].value = req
            r.append(self.do_request(_block))
        return r

    def more_assert(self, first, second, option):
        if 'like' in option:
            assert re.match(first, second)
        elif 'unlike' in option:
            assert not re.match(first, second)
        else:
            self.assertEqual(first, second)

    def assert_response(self, r, item):
        self._exec(item.value)

    def assert_response_body(self, r, item):
        self.more_assert(item.value, r.content, item.option)

    def assert_response_headers(self, r, item):
        headers = get_headers(item.value)
        for k, v in headers.iteritems():
            self.more_assert(v, r.headers[k], item.option)

    def assert_status_code(self, r, item):
        self.more_assert(item.value, str(r.status_code), item.option)

    def assert_error_log(self, _, item):
        if isinstance(item.value, list):
            for p in item.value:
                m = re.search(p, self.error_log)
                assert m, 'error log<%s> not found: %s' % (p, self.error_log)
        else:
            m = re.search(item.value, self.error_log)
            assert m, 'error log<%s> not found: %s' % (item.value,
                                                       self.error_log)

    def assert_no_error_log(self, _, item):
        level = None
        error_level = ['warn', 'error', 'crit', 'alert', 'emerg']
        if isinstance(item.value, str):
            if item.value in error_level:
                level = error_level[error_level.index(item.value):]
            else:
                level = [item.value]
        elif item.value is None:
            level = error_level[1:]
        m = re.search(r'.+?\[(%s)\]' % '|'.join(level), self.error_log)
        assert not m, 'error log found: ' + m.string

    def test_requests(self):
        if self.skip or self.items is None:
            return
        r = None
        for block in self._blocks():
            if isinstance(block, dict):
                if 'request' not in block:
                    continue
                if isinstance(block['request'].value, list):
                    r = self.do_requests(block)
                elif isinstance(block['request'].value, str):
                    r = self.do_request(block)
                if r:
                    self.env['r'] = r
                continue

            assert self.env['r'], 'no request found'
            if 'exec' in block.option:
                self._exec(block.value)
                continue
            if (isinstance(r, list) or isinstance(block.value, list)) and \
                    type(r) != type(block.value):
                raise Exception('unmatched assert')
            if isinstance(r, list):
                for idx, _r in enumerate(r):
                    _block = copy.deepcopy(block)
                    _block.value = block.value[idx]
                    getattr(self, 'assert_' + block.name)(_r, _block)
            else:
                getattr(self, 'assert_' + block.name)(r, block)


def run_tests():
    zts = gather_files(test_directory)
    if not zts:
        return

    suite = unittest.TestSuite()
    for zt in zts:
        _env = {}
        env, cases = Cases()(Lexer()(open(zt).read()))
        if env:
            exec(env, None, _env)
        add_test_case(zt, suite, cases, _env)

    return unittest.TextTestRunner(verbosity=2).run(suite)

unittest_result = run_tests()
if unittest_result and (unittest_result.errors or unittest_result.failures):
    sys.exit(1)
