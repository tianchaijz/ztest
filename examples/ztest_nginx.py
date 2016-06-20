#!/usr/bin/env python
# encoding: utf-8

import os
import re
import sys
import time
import copy
import logging
import unittest
import requests
import subprocess
from subprocess import Popen, PIPE

sys.path.append(os.path.expandvars('$PWD'))

from ztest import Lexer, Cases, ContextTestCase


__version__ = "0.0.3"


request_match = re.compile(
    r'^\s*(?P<method>\w+) (?P<uri>\S+) ?(?P<version>\S+)?(\n|$)'
    r'(?P<headers>(^.+(\n|$))+)?'
    r'(\n(?P<body>([\s\S])+))?', re.M
).match

test_directory = 't/nginx'
openresty_root = '/usr/local/openresty/nginx'
nginx_error_log = 't/nginx/servroot/logs/error.log'
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
    if isinstance(command, list):
        command = ' '.join(command)
    process = Popen(
        args=command,
        stdout=PIPE,
        shell=True
    )

    return process


def system(command):
    if isinstance(command, list):
        command = ' '.join(command)
    return subprocess.call(command, shell=True, close_fds=True)


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
        self = args[0]
        err_log_file = os.path.join(self.nginx_prefix, 'logs/error.log')
        start = file_size(err_log_file)
        r = fn(*args, **kwargs)
        self.error_log += seek_read(err_log_file, start)
        return r
    return wrapper


def sleep(t=0.1):
    time.sleep(t)


def add_test_case(zt, suite, cases, env, run_only=None):
    for case in cases:
        if case.name is None:
            case.name = ''
        if run_only and not re.search(run_only, case.name):
            continue
        case.name = re.sub(r'[^.\w]+', '_', case.name)
        suite.addTest(
            ContextTestCase.addContext(
                type('%s<%s:%s>' % (case.name, zt, case.lineno),
                     (TestNginx,), {}), ctx=Ctx(case, env)))


def get_headers(text):
    headers = {}
    if text is None:
        return headers
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if line:
            k, v = line.split(':', 1)
            headers[k.strip()] = v and v.strip() or ''

    return headers


class LoggingFormatter(logging.Formatter):
    def __init__(self, fmt, datefmt=None):
        logging.Formatter.__init__(self, fmt, datefmt)
        self.converter = time.gmtime

    def formatException(self, exc_info):
        text = logging.Formatter.formatException(self, exc_info)
        text = '\n'.join(('! %s' % line) for line in text.splitlines())
        return text


def get_console_logger(name):
    logging_fmt = '%(levelname)-8s [%(asctime)s] %(name)s: %(message)s'

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(LoggingFormatter(logging_fmt))

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(ch)

    return logger


logger = get_console_logger('ztest')


def LOG_ERR(s):
    logger.log(logging.ERROR, s)


class Ctx(object):
    def __init__(self, case, env):
        self.case = case
        self.env = env


class Nginx(object):
    def __init__(self, prefix, nginx_bin=None):
        self.prefix = prefix
        if nginx_bin:
            self.nginx_bin = nginx_bin
        else:
            self.nginx_bin = os.path.join(self.prefix, 'sbin/nginx')
        self.pid_file = os.path.join(self.prefix, 'logs/nginx.pid')

    def pid(self):
        pid_file = self.pid_file
        if not os.path.isfile(pid_file):
            return None
        try:
            pid = open(pid_file).read().strip()
            int(pid)
        except (IOError, ValueError):
            return None

        p = shell(['ps', '-p', pid])
        out = p.communicate()[0]
        if p.returncode == 0 and out.find('nginx') != -1:
            return pid
        return None

    def start(self):
        if self.pid():
            return
        system('%s -p %s -c %s' % (self.nginx_bin,
               self.prefix, 'conf/nginx.conf'))
        while not self.pid():
            sleep()

    def stop(self):
        pid = self.pid()
        if not pid:
            return
        system('kill -QUIT %s' % pid)
        while self.pid():
            sleep()

    def reload(self, pause=False):
        pid = self.pid()
        if pid:
            system('kill -HUP %s' % pid)
        else:
            self.start()
        if pause:
            sleep(.5)

    def restart(self):
        self.stop()
        self.start()


class TestNginx(ContextTestCase):
    common_items = ['config', 'setup', 'teardown']

    alone_items = ['setenv', 'shell', 'reload_nginx', 'restart_nginx']
    union_items = ['request', 'more_headers', 'request_body']
    assert_items = ['assert', 'response_body', 'response_headers',
                    'status_code', 'no_error_log', 'error_log']
    exec_items = ['assert']

    nginx = None
    nginx_bin = os.path.join(openresty_root, 'sbin/nginx')
    nginx_prefix = os.path.join(os.path.expandvars('$PWD'),
                                test_directory, 'servroot')
    class_name = 'TestNginx'

    def setUp(self):
        self.setup_ = None
        self.teardown_ = None
        self.skip = False

        if self.__class__.__name__ == self.class_name:
            self.skip = True
            return

        self.error_log = ''
        self.locals = {'self': self}
        self.globals = None

        if self.ctx is None or not self.ctx.case:
            raise Exception('no test case found')

        self.name = self.ctx.case.name
        self.items = self.ctx.case.items
        if isinstance(self.ctx.env, dict):
            self.globals = self.ctx.env

        self.nginx = Nginx(self.nginx_prefix, self.nginx_bin)
        self.prepare()

        if self.setup_:
            self.setup_()

        self.start_nginx()

    def tearDown(self):
        if self.teardown_:
            self.teardown_()

    def start_nginx(self, *args):
        self.nginx.start()

    def stop_nginx(self, *args):
        self.nginx.stop()

    def reload_nginx(self, *args):
        self.nginx.reload(True)

    def restart_nginx(self, *args):
        self.nginx.restart()

    def config(self, data):
        servroot = self.nginx.prefix
        logspath = os.path.join(servroot, 'logs')
        confpath = os.path.join(servroot, 'conf')

        system('mkdir -p %s' % logspath)
        system('cp -r %s/conf %s' % (openresty_root, servroot))

        conf = os.path.join(confpath, 'nginx.conf')
        open(conf, 'w+').write(nginx_template % {'config': data})

        self.nginx.reload()
        time.sleep(.2)

    def setup(self, code):
        self.setup_ = lambda: self._exec(code)

    def teardown(self, code):
        self.teardown_ = lambda: self._exec(code)

    def setenv(self, item):
        self._exec(item.value)

    def prepare(self):
        for idx, item in enumerate(self.items):
            if item.name in self.common_items:
                self.eval_item(item)
                getattr(self, item.name)(item.value)
            else:
                break
        self.items = self.items[idx:]

    def _blocks(self):
        block = {}
        for item in self.items:
            self.eval_item(item)
            if item.name in self.union_items:
                if item.name in block:
                    yield block
                    block = {}
                block[item.name] = item
            else:
                if block:
                    yield block
                    block = {}
                yield item

    def eval_item(self, item):
        if 'eval' in item.option:
            item.value = self._eval(item.value)

    def _exec(self, code):
        exec(code, self.globals, self.locals)

    def _eval(self, code):
        return eval(code, self.globals, self.locals)

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

        allow_redirects = False
        if 'allow_redirects' in block:
            allow_redirects = True

        headers = get_headers(headers)
        method, uri = m.group('method'), m.group('uri')
        if uri.startswith('/'):
            uri = 'http://%s%s' % (nginx_api, uri)
        elif not re.match(r'https?://'):
            uri = 'http://%s/%s' % (nginx_api, uri)
        return getattr(requests, method.lower())(
                       uri, headers=headers, data=body,
                       allow_redirects=allow_redirects)

    def do_requests(self, block):
        r = []
        for req in block['request'].value:
            if not isinstance(req, str):
                raise Exception('unexpected request type: ' + type(req))
            _block = copy.deepcopy(block)
            _block['request'].value = req
            r.append(self.do_request(_block))
        return r

    def more_assert(self, pattern, text, option):
        if 'like' in option:
            assert re.search(pattern, text), text
        elif 'unlike' in option:
            assert not re.search(pattern, text), text
        else:
            self.assertEqual(pattern, text)

    def assert_response_body(self, r, item):
        self.more_assert(item.value, r.content, item.option)

    def assert_response_headers(self, r, item):
        headers = get_headers(item.value)
        for k, v in headers.iteritems():
            self.more_assert(v, r.headers[k], item.option)

    def assert_status_code(self, r, item):
        self.more_assert(int(item.value), r.status_code, item.option)

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

    def do_assert(self, item):
        if item.name in self.exec_items or 'exec' in item.option:
            return self._exec(item.value)

        r = self.locals['r']
        assert r is not None, 'no request found'

        if (isinstance(r, list) or isinstance(item.value, list)) and \
                not isinstance(r, type(item.value)):
            raise Exception('unmatched assert')
        if isinstance(r, list):
            for idx, _r in enumerate(r):
                _item = copy.deepcopy(item)
                _item.value = item.value[idx]
                getattr(self, 'assert_' + item.name)(_r, _item)
        else:
            getattr(self, 'assert_' + item.name)(r, item)

    def test_run(self):
        if self.skip or self.items is None:
            return
        for block in self._blocks():
            if isinstance(block, dict):
                if block.get('request') is None:
                    raise Exception('no request found')
                if isinstance(block['request'].value, list):
                    r = self.do_requests(block)
                elif isinstance(block['request'].value, str):
                    r = self.do_request(block)
                self.locals['r'] = r
            elif block.name in self.alone_items:
                getattr(self, block.name)(block)
            else:
                try:
                    self.do_assert(block)
                except:
                    LOG_ERR('%s at line: %d' % (block.name, block.lineno))
                    raise


def run_test_suite(suite):
    r = unittest.TextTestRunner(verbosity=2).run(suite)
    if r and (r.errors or r.failures):
        sys.exit(1)


def run_tests():
    td = os.environ.get('ZTEST_DIR')
    if td is None:
        td = test_directory

    zts = gather_files(td)
    if not zts:
        return

    for zt in zts:
        env, suite = {'TestNginx': TestNginx}, unittest.TestSuite()
        g, cases = Cases()(Lexer()(open(zt).read()))

        if g.get('env'):
            exec(g['env'], env, None)
        if g.get('setup'):
            exec(g['setup'], env, None)

        run_only = os.environ.get('ZTEST_RUN_ONLY')
        add_test_case(zt, suite, cases, env, run_only=run_only)

        try:
            run_test_suite(suite)
        finally:
            if g.get('teardown'):
                exec(g['teardown'], env, None)


run_tests()
