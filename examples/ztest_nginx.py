#!/usr/bin/env python
# encoding: utf-8

import os
import re
import sys
import time
import unittest
import requests
from subprocess import Popen, PIPE

sys.path.append(os.path.expandvars('$PWD'))

from ztest import Lexer, Cases, ContextTestCase

request_pattern = re.compile(
    r'^(?P<method>\w+) (?P<uri>\S+) ?(?P<version>\S+)?(?:\n|$)'
    r'(?:\n(?P<headers>(?:.+(?:\n|$))+))?'
    r'(?:\n(?P<body>(?:[\s\S])+))?', re.M
)

test_directory = 't'
openresty_root = '/usr/local/openresty/nginx'
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


def restore_global_env(env):
    global_env = globals()
    keys = global_env.keys()
    for k in keys:
        if k in env:
            global_env[k] = env[k]
        else:
            del global_env[k]


def gather_files(test_dir):
    if os.path.isfile(test_dir):
        return [test_dir] if test_dir.endswith('zt') else []

    test_files = []
    for d, _, files in os.walk(test_dir):
        test_files.extend(os.path.join(d, f) for f in
                          filter(lambda f: f.endswith('zt'), files))

    return test_files


def add_test_case(zt, cases, suite):
    for case in cases:
        if case.name is None:
            case.name = ''
        suite.addTest(
            ContextTestCase.addContext(
                type('[%s] in <%s>' % (case.name, zt), (TestNginx,), {}),
                ctx={'case': case}))


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


class TestNginx(ContextTestCase):
    common_items = ['config', 'setup', 'teardown', 'setenv']
    assert_items = ['response', 'response_body', 'response_headers',
                    'status_code']
    block_items = ['request', 'more_headers', 'request_body'] + assert_items
    items = common_items + block_items

    def setUp(self):
        self.setup_ = None
        self.teardown_ = None
        self.skip = False
        self.env = {'_': self}

        if self.__class__.__name__ == 'TestNginx':
            self.skip = True
            return

        if self.ctx is None or not self.ctx['case']:
            raise Exception('no test case found')

        self.name = self.ctx['case'].name
        self.items = self.ctx['case'].items

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
            item_name = item['name']
            assert item_name in TestNginx.items, 'unknown item: %s' % item_name
            if item_name in TestNginx.common_items:
                if 'eval' in item:
                    item['value'] = eval(item['value'], globals(), self.env)
                getattr(self, item['name'])(item['value'])
            if item_name in TestNginx.block_items:
                break
        self.items = self.items[idx:]

    def _blocks(self):
        block = {}
        for item in self.items:
            item_name = item['name']
            assert item_name in TestNginx.block_items, \
                'unknown block item: %s' % item_name
            if 'eval' in item:
                item['value'] = eval(item['value'], globals(), self.env)
            if item_name in block:
                yield block
                block = {}
            block[item_name] = item
        if block:
            yield block

    def _exec(self, code):
        exec(code, globals(), self.env)

    def do_request(self, block):
        request = block['request']
        if 'exec' in request:
            return self._exec(request['value'])

        m = request_pattern.match(request['value'])
        assert m, "invalid request block"

        headers, body = m.group('headers'), m.group('body')
        if 'more_headers' in block:
            if headers is None:
                headers = block['more_headers']['value']
            else:
                headers += '\n' + block['more_headers']['value']
        if 'request_body' in block:
            if body is None:
                body = block['request_body']['value']
            else:
                body += block['request_body']['value']

        headers = get_headers(headers)
        method, uri = m.group('method'), m.group('uri')
        if uri.startswith('/'):
            uri = 'http://%s%s' % (nginx_api, uri)
        elif not re.match(r'https?://'):
            uri = 'http://%s/%s' % (nginx_api, uri)
        r = getattr(requests, method.lower())(uri, headers=headers, data=body)
        self.env['r'] = r

        for name in TestNginx.assert_items:
            if name not in block:
                continue
            item = block[name]
            getattr(self, 'assert_' + name)(r, item)

    def more_assert(self, first, second, like=False):
        if like:
            assert re.match(first, second)
        else:
            self.assertEqual(first, second)

    def assert_response(self, r, item):
        self._exec(item['value'])

    def assert_response_body(self, r, item):
        self.more_assert(item['value'], r.content, 'like' in item)

    def assert_response_headers(self, r, item):
        like = 'like' in item
        headers = get_headers(item['value'])
        for k, v in headers.iteritems():
            self.more_assert(v, r.headers[k], like)

    def assert_status_code(self, r, item):
        self.more_assert(item['value'], str(r.status_code), 'like' in item)

    def test_requests(self):
        if self.skip or self.items is None:
            return
        for block in self._blocks():
            if 'request' not in block:
                continue
            self.do_request(block)


def run_test():
    default_env, global_env = {}, globals()
    for k in global_env.keys():
        default_env[k] = global_env[k]

    zts = gather_files(test_directory)
    if not zts:
        return

    suite = unittest.TestSuite()

    for zt in zts:
        restore_global_env(default_env)
        preamble, cases = Cases()(Lexer()(open(zt).read()))
        if preamble:
            exec(preamble, None, globals())
        add_test_case(zt, cases, suite)

    return unittest.TextTestRunner(verbosity=2).run(suite)

unittest_result = run_test()
if unittest_result and unittest_result.errors:
    sys.exit(1)
