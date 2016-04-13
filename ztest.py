#!/usr/bin/env python
# encoding: utf-8

"""
    ztest
    ~~~~~

    A unit test framework inspired by Test::Nginx.
"""

from __future__ import print_function

import re

__version__ = '0.0.1'
__author__ = 'Jinzheng Zhang <tianchaijz@gmail.com>'
__all__ = [
    'Pattern', 'Lexer', 'LexException'
]


class Pattern(object):
    """Patterns for ztest."""

    case_line_pattern = r'^=== TEST (\d+): ?(.+)?$'
    item_pattern = r'^--- (\w+) ?(eval|exec)?'
    item_line_pattern = r'%s: (.+)$' % item_pattern
    item_head_pattern = r'%s$' % item_pattern

    comment_line = re.compile(r'^\s*(//|#).*$', re.M)
    blank_line = re.compile(r'^\s*\n+')
    preamble = re.compile(
        r'([\s\S]*)'
        r'^__DATA__(?:\n*|$)', re.M
    )
    case_line = re.compile(case_line_pattern, re.M)
    item_line = re.compile(item_line_pattern, re.M)
    item_head = re.compile(item_head_pattern, re.M)
    item_block = re.compile(r'%s|%s|%s' % (
        case_line_pattern,
        item_line_pattern,
        item_head_pattern), re.M
    )  # reversed

    string_block = re.compile(
        r'^\s*(\'{3,}|"{3,}|`{3,})'
        r'([\s\S]+)'
        r'\1\s*(?:\n*|$)'
    )


def lex_decorator(fn):
    def wrapper(*args, **kwargs):
        if isinstance(args[1], str):
            text = args[1]
        else:
            text = args[1].group(0)
        self = args[0]
        self.lineno += text.count('\n')
        if self.verbose:
            print('[%s]: %s' % (fn.__name__, text))
        return fn(*args, **kwargs)
    return wrapper


class Lexer(object):
    """Lexer for ztest."""

    rules = ['comment_line', 'blank_line', 'case_line',
             'item_line', 'item_head',
             'string_block', 'item_block']

    PREAMBLE = 1
    NEXT = 2
    CASE_LINE = 3
    ITEM = 4
    ITEM_HEAD = 5
    ITEM_BLOCK = 6

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.state = self.PREAMBLE
        self.lineno = 0
        self.tokens = []

    def __call__(self, text):
        return self.lex(text)

    def append(self, token):
        self.state = token['type']
        if self.verbose:
            print('[%s] got token: %s' % (self.__class__, token))
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
            if self.state == self.PREAMBLE and Pattern.preamble.match(text):
                m = process(text, 'preamble')
                self.state = self.NEXT
            else:
                for key in self.rules:
                    m = process(text, key)
                    if m is not None:
                        break
            if m is None:
                raise LexException('unexpected text: %s' % text)

            if isinstance(m, int):
                position = m
            else:
                position = len(m.group(0))
            text = text[position:]

        for token in self.tokens:
            if token['type'] == self.ITEM_HEAD:
                token['type'] = self.ITEM

        return self.tokens

    @lex_decorator
    def lex_blank_line(self, m):
        pass  # skip blank lines

    @lex_decorator
    def lex_comment_line(self, m):
        pass  # skip comment

    @lex_decorator
    def lex_preamble(self, m):
        self.append({
            'type': self.PREAMBLE,
            'value': m.group(1)
        })

    @lex_decorator
    def lex_case_line(self, m):
        self.append({
            'type': self.CASE_LINE,
            'order': m.group(1),
            'value': m.group(2)
        })

    @lex_decorator
    def lex_item_line(self, m):
        token = {
            'type': self.ITEM,
            'item': m.group(1),
            'value': m.group(3).strip()
        }

        if m.group(2):
            token[m.group(2)] = True
        self.append(token)

    @lex_decorator
    def lex_item_head(self, m):
        token = {
            'type': self.ITEM_HEAD,
            'item': m.group(1),
            'value': None
        }

        if m.group(2):
            token[m.group(2)] = True
        self.append(token)

    @lex_decorator
    def lex_item_block(self, text):
        if len(self.tokens) == 0 or \
                self.tokens[-1]['type'] != self.ITEM_HEAD:
            raise LexException('unexpected block: %s' % text)

        m = Pattern.item_block.search(text)
        if m is None:
            position = len(text)
        else:
            position = m.start()
        self.tokens[-1]['type'] = self.ITEM
        self.tokens[-1]['value'] = text[0:position - 1].strip()

        return position

    @lex_decorator
    def lex_string_block(self, m):
        if len(self.tokens) == 0 or \
                self.tokens[-1]['type'] != self.ITEM_HEAD:
            raise LexException('unexpected string: %s' % m.group(0))

        self.tokens[-1]['type'] = self.ITEM
        self.tokens[-1]['value'] = m.group(2)


class LexException(Exception):
    pass
