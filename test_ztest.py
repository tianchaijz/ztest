import unittest
from ztest import Lexer, LexException


def get_tokens(verbose=False, raises=None, raises_regexp=None):
    def wrapper(fn):
        def wrapped(*args, **kwargs):
            lexer = Lexer(verbose=verbose)
            assert fn.__doc__
            if raises:
                if raises_regexp:
                    args[0].assertRaisesRegexp(raises, raises_regexp,
                                               lexer, fn.__doc__)
                else:
                    args[0].assertRaises(raises, lexer, fn.__doc__)
            else:
                kwargs['tokens'] = lexer(fn.__doc__)
                return fn(*args, **kwargs)
        return wrapped
    return wrapper


class TestZtest(unittest.TestCase):
    @get_tokens()
    def test_preamble_00(self, tokens=None):
        '''import sys
__DATA__'''
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0]['lineno'], 1)
        self.assertEqual(tokens[0]['type'], Lexer.PREAMBLE)
        self.assertEqual(tokens[0]['value'], '''import sys
''')

    @get_tokens()
    def test_preamble_01(self, tokens=None):
        '''
import sys

__DATA__'''
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0]['lineno'], 1)
        self.assertEqual(tokens[0]['type'], Lexer.PREAMBLE)
        self.assertEqual(tokens[0]['value'], '''
import sys

''')

    @get_tokens()
    def test_preamble_02(self, tokens=None):
        '''
import sys

__DATA__
'''
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0]['lineno'], 1)
        self.assertEqual(tokens[0]['type'], Lexer.PREAMBLE)
        self.assertEqual(tokens[0]['value'], '''
import sys

''')

    @get_tokens()
    def test_preamble_03(self, tokens=None):
        '''
import sys

__DATA__

'''
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0]['lineno'], 1)
        self.assertEqual(tokens[0]['type'], Lexer.PREAMBLE)
        self.assertEqual(tokens[0]['value'], '''
import sys

''')

    @get_tokens()
    def test_case_00(self, tokens=None):
        '''
import sys

__DATA__

=== TEST 1: sanity
'''
        self.assertEqual(len(tokens), 2)

        self.assertEqual(tokens[0]['lineno'], 1)
        self.assertEqual(tokens[0]['type'], Lexer.PREAMBLE)
        self.assertEqual(tokens[0]['value'], '''
import sys

''')
        self.assertEqual(tokens[1]['lineno'], 6)
        self.assertEqual(tokens[1]['type'], Lexer.CASE_LINE)
        self.assertEqual(tokens[1]['value'], 'sanity')
        self.assertEqual(tokens[1]['order'], '1')

    @get_tokens()
    def test_case_01(self, tokens=None):
        '''
import sys

__DATA__

=== TEST 1: sanity
--- request
'''
        self.assertEqual(len(tokens), 3)

        self.assertEqual(tokens[2]['lineno'], 7)
        self.assertEqual(tokens[2]['type'], Lexer.ITEM)
        self.assertEqual(tokens[2]['item'], 'request')

    @get_tokens()
    def test_case_02(self, tokens=None):
        '''
import sys

__DATA__

=== TEST 1: sanity
--- request eval
GET /
'''
        self.assertEqual(len(tokens), 3)

        self.assertEqual(tokens[2]['lineno'], 7)
        self.assertEqual(tokens[2]['type'], Lexer.ITEM)
        self.assertEqual(tokens[2]['item'], 'request')
        self.assertEqual(tokens[2]['value'], 'GET /')
        self.assertEqual(tokens[2]['eval'], True)

    @get_tokens()
    def test_case_03(self, tokens=None):
        '''
=== TEST 1: sanity
--- request eval
GET /
'''
        self.assertEqual(len(tokens), 2)

        self.assertEqual(tokens[0]['lineno'], 2)

        self.assertEqual(tokens[1]['lineno'], 3)
        self.assertEqual(tokens[1]['type'], Lexer.ITEM)
        self.assertEqual(tokens[1]['item'], 'request')
        self.assertEqual(tokens[1]['value'], 'GET /')
        self.assertEqual(tokens[1]['eval'], True)

    @get_tokens()
    def test_case_04(self, tokens=None):
        '''
=== TEST 1: sanity
--- request: GET /
'''
        self.assertEqual(len(tokens), 2)

        self.assertEqual(tokens[1]['lineno'], 3)
        self.assertEqual(tokens[1]['type'], Lexer.ITEM)
        self.assertEqual(tokens[1]['item'], 'request')
        self.assertEqual(tokens[1]['value'], 'GET /')

    @get_tokens()
    def test_case_05(self, tokens=None):
        '''
=== TEST 1: sanity
--- request eval: GET /
'''
        self.assertEqual(len(tokens), 2)

        self.assertEqual(tokens[1]['lineno'], 3)
        self.assertEqual(tokens[1]['type'], Lexer.ITEM)
        self.assertEqual(tokens[1]['item'], 'request')
        self.assertEqual(tokens[1]['value'], 'GET /')
        self.assertEqual(tokens[1]['eval'], True)

    @get_tokens()
    def test_case_06(self, tokens=None):
        '''
=== TEST 1: sanity 1
--- request eval: GET /

=== TEST 2: sanity 2
'''
        self.assertEqual(len(tokens), 3)

        self.assertEqual(tokens[2]['lineno'], 5)
        self.assertEqual(tokens[2]['type'], Lexer.CASE_LINE)
        self.assertEqual(tokens[2]['value'], 'sanity 2')
        self.assertEqual(tokens[2]['order'], '2')

    @get_tokens()
    def test_case_07(self, tokens=None):
        '''
=== TEST 1: sanity 1
--- request eval: GET /

=== TEST 2: sanity 2
--- request
GET /
'''
        self.assertEqual(len(tokens), 4)

        self.assertEqual(tokens[3]['lineno'], 6)
        self.assertEqual(tokens[3]['type'], Lexer.ITEM)
        self.assertEqual(tokens[3]['item'], 'request')
        self.assertEqual(tokens[3]['value'], 'GET /')

    @get_tokens()
    def test_case_08(self, tokens=None):
        '''
=== TEST 1: sanity 1
--- request eval: GET /
--- response_body
hello

=== TEST 2: sanity 2
--- request
GET /

--- response_body

world
'''
        self.assertEqual(len(tokens), 6)

        self.assertEqual(tokens[2]['lineno'], 4)
        self.assertEqual(tokens[2]['type'], Lexer.ITEM)
        self.assertEqual(tokens[2]['item'], 'response_body')
        self.assertEqual(tokens[2]['value'], 'hello')

        self.assertEqual(tokens[5]['lineno'], 11)
        self.assertEqual(tokens[5]['type'], Lexer.ITEM)
        self.assertEqual(tokens[5]['item'], 'response_body')
        self.assertEqual(tokens[5]['value'], 'world')

    @get_tokens()
    def test_case_09(self, tokens=None):
        '''
=== TEST 1: sanity 1
--- request eval: GET /
--- request_headers
Host: www.google.com

--- response_body
```
hello

```
'''
        self.assertEqual(len(tokens), 4)

        self.assertEqual(tokens[3]['lineno'], 7)
        self.assertEqual(tokens[3]['type'], Lexer.ITEM)
        self.assertEqual(tokens[3]['item'], 'response_body')
        self.assertEqual(tokens[3]['value'], '''
hello

''')

    @get_tokens()
    def test_case_10(self, tokens=None):
        '''
# this is a comment
=== TEST 1: sanity 1
--- request eval: GET /

=== TEST 2: sanity 2
// this is a comment
# this is a comment too
--- request eval: GET /
'''
        self.assertEqual(len(tokens), 4)

        self.assertEqual(tokens[1]['lineno'], 4)

        self.assertEqual(tokens[3]['lineno'], 9)
        self.assertEqual(tokens[3]['type'], Lexer.ITEM)
        self.assertEqual(tokens[3]['item'], 'request')
        self.assertEqual(tokens[3]['value'], 'GET /')

    @get_tokens()
    def test_case_11(self, tokens=None):
        '''
import sys

__DATA__
=== TEST 1: sanity

--- http_config
gzip on;

--- request
GET /
--- response_body_like
^Hello [a-z]$

--- request
GET /
--- response_body
Hello World

=== TEST 2:
--- request eval: GET /
'''

        self.assertEqual(len(tokens), 9)

        self.assertEqual(tokens[4]['lineno'], 12)
        self.assertEqual(tokens[4]['type'], Lexer.ITEM)
        self.assertEqual(tokens[4]['item'], 'response_body_like')
        self.assertEqual(tokens[4]['value'], '^Hello [a-z]$')

        self.assertEqual(tokens[7]['lineno'], 20)
        self.assertEqual(tokens[7]['type'], Lexer.CASE_LINE)
        self.assertEqual(tokens[7]['order'], '2')
        self.assertEqual(tokens[7]['value'], None)

    @get_tokens()
    def test_case_12(self, tokens=None):
        '''
import sys

__DATA__

=== TEST 1: sanity

--- http_config
# pass
--- server_config

--- request
--- response_body_like
^Hello
--- error_code
'''

        self.assertEqual(len(tokens), 7)

        self.assertEqual(tokens[3]['lineno'], 10)
        self.assertEqual(tokens[3]['type'], Lexer.ITEM)
        self.assertEqual(tokens[3]['item'], 'server_config')
        self.assertEqual(tokens[3]['value'], None)

        self.assertEqual(tokens[5]['lineno'], 13)
        self.assertEqual(tokens[5]['type'], Lexer.ITEM)
        self.assertEqual(tokens[5]['item'], 'response_body_like')
        self.assertEqual(tokens[5]['value'], '^Hello')

        self.assertEqual(tokens[6]['lineno'], 15)
        self.assertEqual(tokens[6]['type'], Lexer.ITEM)
        self.assertEqual(tokens[6]['item'], 'error_code')
        self.assertEqual(tokens[6]['value'], None)

    @get_tokens()
    def test_string_block_00(self, tokens=None):
        '''
=== TEST 1: sanity
--- request eval
"""
"""
GET ''.join(['1'*1, '2*2, '3'*3])
"""
"""
'''

        self.assertEqual(len(tokens), 2)

        self.assertEqual(tokens[1]['lineno'], 3)
        self.assertEqual(tokens[1]['type'], Lexer.ITEM)
        self.assertEqual(tokens[1]['item'], 'request')
        self.assertEqual(tokens[1]['eval'], True)
        self.assertEqual(tokens[1]['value'], '''
"""
GET ''.join(['1'*1, '2*2, '3'*3])
"""
''')

    @get_tokens()
    def test_string_block_01(self, tokens=None):
        '''
=== TEST 1: sanity
--- request eval
```"""
GET ''.join(['/', '1'*1, '2'*2, '3'*3])
"""```
'''

        self.assertEqual(len(tokens), 2)

        self.assertEqual(tokens[1]['lineno'], 3)
        self.assertEqual(tokens[1]['type'], Lexer.ITEM)
        self.assertEqual(tokens[1]['item'], 'request')
        self.assertEqual(tokens[1]['eval'], True)
        self.assertEqual(tokens[1]['value'], '''"""
GET ''.join(['/', '1'*1, '2'*2, '3'*3])
"""''')

    @get_tokens(raises=LexException, raises_regexp='unexpected block: 1')
    def test_exception_00(self, tokens=None):
        '''
import sys

__DATA__

1'''

    @get_tokens(raises=LexException,
                raises_regexp='unexpected string: ```1```')
    def test_exception_01(self, tokens=None):
        '''
import sys

__DATA__

```1```
'''

if __name__ == '__main__':
    unittest.main()
