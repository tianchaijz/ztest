#!/usr/bin/env python
# encoding: utf-8

"""
    ztest
    ~~~~~

    A unit test framework inspired by Test::Nginx.
"""

from __future__ import print_function

import re
import os
import unittest

__version__ = '0.0.3'
__author__ = 'Jinzheng Zhang <tianchaijz@gmail.com>'
__all__ = [
    'Pattern', 'Lexer', 'LexerException', 'Cases', 'ContextTestCase'
]


class Pattern(object):
    """ Patterns for ztest.
    """

    comment_pattern = r'^\s*//.*$'
    delimiter_pattern = '(?P<delimiter>__EOF__)$'
    case_line_pattern = r'^=== (TEST (\d+(\.\d+)?): ?(.+)?)$'
    item_pattern = r'^--- (\w+) ?((?:\w+ ?)*)'
    item_line_pattern = r'%s: (.+)$' % item_pattern
    item_head_pattern = r'%s$' % item_pattern

    comment_line = re.compile(comment_pattern, re.M)
    blank_line = re.compile(r'^\s*\n+')
    case_line = re.compile(case_line_pattern, re.M)
    item_line = re.compile(item_line_pattern, re.M)
    item_head = re.compile(item_head_pattern, re.M)
    item_block = re.compile(r'%s|%s|%s|%s|%s' % (
        comment_pattern,
        delimiter_pattern,
        case_line_pattern,
        item_line_pattern,
        item_head_pattern), re.M
    )  # reversed

    string_block = re.compile(
        r'^\s*([`~,;%@><]{3,})'
        r'([\s\S]+?)'
        r'\1\s*(?:\n*|$)'
    )


def lex_decorator(fn):
    def wrapper(*args, **kwargs):
        self = args[0]
        self.blineno = self.elineno
        position = fn(*args, **kwargs)
        if isinstance(position, int):
            text = args[1][0:position]
        else:
            text = args[1].group(0)
        if self.verbose:
            print('<%s>: %s' % (fn.__name__, text))
        self.elineno += text.count('\n')

        return position
    return wrapper


class Token(object):
    types = ["GLOBAL", "CASE_LINE",
             "ITEM", "ITEM_HEAD", "ITEM_BLOCK"]

    def __init__(self, type, name, **kwargs):
        self.type = type
        self.name = name
        self.value = None
        self.lineno = 0

        for k, v in kwargs.iteritems():
            setattr(self, k, v)

    def __str__(self):
        if hasattr(self, 'option'):
            return "Token<%s %s %r>(%s) at line: %d" % \
                (Token.types[self.type], self.name, self.option, self.value,
                 self.lineno)
        else:
            return "Token<%s %s>(%s) at line: %d" % \
                (Token.types[self.type], self.name, self.value, self.lineno)

    def __repr__(self):
        return self.__str__()


class Lexer(object):
    """ Lexer for ztest.
    """

    rules = ['comment_line', 'blank_line', 'case_line',
             'item_line', 'item_head',
             'string_block', 'item_block']

    GLOBAL = 0
    CASE_LINE = 1
    ITEM = 2
    ITEM_HEAD = 3
    ITEM_BLOCK = 4

    def __init__(self, verbose=False):
        self.state = self.GLOBAL
        self.blineno = 0
        self.elineno = 1
        self.tokens = []

        if os.environ.get('ZTEST_VERBOSE') == '1':
            self.verbose = True
        else:
            self.verbose = verbose

    def __call__(self, text):
        return self.lex(text)

    @staticmethod
    def get_item_option(s):
        return filter(lambda x: x != '', s.strip().split(' '))

    def append(self, token):
        self.state = token.type
        token.lineno = self.blineno
        if self.verbose:
            print('%s %s' % (self.__class__, token))
        self.tokens.append(token)

    def lex(self, text):
        def process(text, key):
            if key == 'item_block':
                m = self.lex_item_block(text)
            else:
                m = getattr(Pattern, key).match(text)
                if m:
                    getattr(self, 'lex_' + key)(m)
            return m

        while text:
            m, position = None, None
            for key in self.rules:
                m = process(text, key)
                if m is not None:
                    break
            if m is None:
                raise LexerException('unexpected text: %s' % text)

            if isinstance(m, int):
                position = m
            else:
                position = len(m.group(0))
            text = text[position:]

        seen_case_line = False
        for token in self.tokens:
            if token.type == Lexer.CASE_LINE and not seen_case_line:
                seen_case_line = True
                continue
            if token.type == self.ITEM_HEAD:
                token.type = self.ITEM
            if not seen_case_line and token.type == Lexer.ITEM:
                token.type = Lexer.GLOBAL

        return self.tokens

    @lex_decorator
    def lex_blank_line(self, m):
        pass  # skip blank lines

    @lex_decorator
    def lex_comment_line(self, m):
        pass  # skip comment

    @lex_decorator
    def lex_case_line(self, m):
        self.append(Token(
            self.CASE_LINE,
            m.group(1)
        ))

    @lex_decorator
    def lex_item_line(self, m):
        token = Token(
            self.ITEM,
            m.group(1),
            option=[],
            value=m.group(3).strip()
        )

        if m.group(2):
            token.option = Lexer.get_item_option(m.group(2))
        self.append(token)

    @lex_decorator
    def lex_item_head(self, m):
        token = Token(
            self.ITEM_HEAD,
            m.group(1),
            option=[]
        )

        if m.group(2):
            token.option = Lexer.get_item_option(m.group(2))
        self.append(token)

    @lex_decorator
    def lex_item_block(self, text):
        if len(self.tokens) == 0 or \
                self.tokens[-1].type != self.ITEM_HEAD:
            raise LexerException('unexpected block: %s' % text)

        m = Pattern.item_block.search(text)
        if m is None:
            position = len(text)
        else:
            position = m.start()

        if m and m.group('delimiter'):
            self.tokens[-1].value = text[0:position]
            position += len(m.group('delimiter'))
        else:
            self.tokens[-1].value = text[0:position].strip()
        self.tokens[-1].type = self.ITEM

        return position

    @lex_decorator
    def lex_string_block(self, m):
        if len(self.tokens) == 0 or \
                self.tokens[-1].type != self.ITEM_HEAD:
            raise LexerException('unexpected string: %s' % m.group(0))

        self.tokens[-1].type = self.ITEM
        self.tokens[-1].value = m.group(2)


class LexerException(Exception):
    pass


class Case(object):
    def __init__(self, name, lineno, items):
        self.name = name
        self.lineno = lineno
        self.items = items

    def __str__(self):
        return '<%s>: %s' % (self.name, self.items)

    def __repr__(self):
        return self.__str__()


class Cases(object):
    def __init__(self):
        self.globals = {}
        self.cases = []

    def __call__(self, tokens):
        self.parse(tokens)
        return (self.globals, self.cases)

    def parse(self, tokens):
        name, lineno, items = None, 0, []
        for token in tokens:
            if token.type == Lexer.GLOBAL:
                self.globals[token.name] = token.value
            if token.type == Lexer.ITEM:
                items.append(token)
            if token.type == Lexer.CASE_LINE:
                if items:
                    self.cases.append(Case(name, lineno, items))
                    items = []
                name, lineno = token.name, token.lineno
        if items:
            self.cases.append(Case(name, lineno, items))


class ContextTestCase(unittest.TestCase):
    """ TestCase classes that want a context should
        inherit from this class.
    """
    def __init__(self, methodName='runTest', ctx=None):
        super(ContextTestCase, self).__init__(methodName)
        self.ctx = ctx

    @staticmethod
    def addContext(testClass, ctx=None):
        """ Create a suite containing all tests taken from the given
            subclass, passing them the context.
        """
        loader = unittest.TestLoader()
        cases = loader.getTestCaseNames(testClass)
        suite = unittest.TestSuite()
        for case in cases:
            suite.addTest(testClass(case, ctx=ctx))
        return suite
