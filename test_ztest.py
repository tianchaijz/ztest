import unittest
from functools import wraps
from ztest import Lexer, LexException, Cases


def get_tokens(verbose=False, raises=None, raises_regexp=None):
    def wrapper(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            assert fn.__doc__
            self, lexer = args[0], Lexer(verbose=verbose)
            if raises:
                if raises_regexp:
                    self.assertRaisesRegexp(raises, raises_regexp,
                                            lexer, fn.__doc__)
                else:
                    self.assertRaises(raises, lexer, fn.__doc__)
            else:
                kwargs['tokens'] = lexer(fn.__doc__)
                return fn(*args, **kwargs)
        return wrapped
    return wrapper


def get_cases(verbose=False):
    def wrapper(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            assert fn.__doc__
            lexer = Lexer(verbose=verbose)
            tokens = lexer(fn.__doc__)
            kwargs['preamble'], kwargs['cases'] = Cases()(tokens)
            return fn(*args, **kwargs)
        return wrapped
    return wrapper


class TestZtest(unittest.TestCase):
    @get_tokens()
    def test_preamble_00(self, tokens=None):
        '''import sys
__DATA__'''
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].lineno, 1)
        self.assertEqual(tokens[0].type, Lexer.PREAMBLE)
        self.assertEqual(tokens[0].value, '''import sys
''')

    @get_tokens()
    def test_preamble_01(self, tokens=None):
        '''
import sys

__DATA__'''
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].lineno, 1)
        self.assertEqual(tokens[0].type, Lexer.PREAMBLE)
        self.assertEqual(tokens[0].value, '''
import sys

''')

    @get_tokens()
    def test_preamble_02(self, tokens=None):
        '''
import sys

__DATA__
'''
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].lineno, 1)
        self.assertEqual(tokens[0].type, Lexer.PREAMBLE)
        self.assertEqual(tokens[0].value, '''
import sys

''')

    @get_tokens()
    def test_preamble_03(self, tokens=None):
        '''
import sys

__DATA__

'''
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].lineno, 1)
        self.assertEqual(tokens[0].type, Lexer.PREAMBLE)
        self.assertEqual(tokens[0].value, '''
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

        self.assertEqual(tokens[0].lineno, 1)
        self.assertEqual(tokens[0].type, Lexer.PREAMBLE)
        self.assertEqual(tokens[0].value, '''
import sys

''')
        self.assertEqual(tokens[1].lineno, 6)
        self.assertEqual(tokens[1].type, Lexer.CASE_LINE)
        self.assertEqual(tokens[1].name, 'TEST 1: sanity')

    @get_tokens()
    def test_case_01(self, tokens=None):
        '''
import sys

__DATA__

=== TEST 1: sanity
--- request
'''
        self.assertEqual(len(tokens), 3)

        self.assertEqual(tokens[2].lineno, 7)
        self.assertEqual(tokens[2].type, Lexer.ITEM)
        self.assertEqual(tokens[2].name, 'request')

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

        self.assertEqual(tokens[2].lineno, 7)
        self.assertEqual(tokens[2].type, Lexer.ITEM)
        self.assertEqual(tokens[2].name, 'request')
        self.assertEqual(tokens[2].value, 'GET /')
        self.assertEqual(tokens[2].option, ['eval'])

    @get_tokens()
    def test_case_03(self, tokens=None):
        '''
=== TEST 1: sanity
--- request eval
GET /
'''
        self.assertEqual(len(tokens), 2)

        self.assertEqual(tokens[0].lineno, 2)

        self.assertEqual(tokens[1].lineno, 3)
        self.assertEqual(tokens[1].type, Lexer.ITEM)
        self.assertEqual(tokens[1].name, 'request')
        self.assertEqual(tokens[1].value, 'GET /')
        self.assertEqual(tokens[1].option, ['eval'])

    @get_tokens()
    def test_case_04(self, tokens=None):
        '''
=== TEST 1: sanity
--- request: GET /
'''
        self.assertEqual(len(tokens), 2)

        self.assertEqual(tokens[1].lineno, 3)
        self.assertEqual(tokens[1].type, Lexer.ITEM)
        self.assertEqual(tokens[1].name, 'request')
        self.assertEqual(tokens[1].value, 'GET /')

    @get_tokens()
    def test_case_05(self, tokens=None):
        '''
=== TEST 1: sanity
--- request eval: GET /
'''
        self.assertEqual(len(tokens), 2)

        self.assertEqual(tokens[1].lineno, 3)
        self.assertEqual(tokens[1].type, Lexer.ITEM)
        self.assertEqual(tokens[1].name, 'request')
        self.assertEqual(tokens[1].value, 'GET /')
        self.assertEqual(tokens[1].option, ['eval'])

    @get_tokens()
    def test_case_06(self, tokens=None):
        '''
=== TEST 1: sanity 1
--- request eval: GET /

=== TEST 2: sanity 2
'''
        self.assertEqual(len(tokens), 3)

        self.assertEqual(tokens[2].lineno, 5)
        self.assertEqual(tokens[2].type, Lexer.CASE_LINE)
        self.assertEqual(tokens[2].name, 'TEST 2: sanity 2')

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

        self.assertEqual(tokens[3].lineno, 6)
        self.assertEqual(tokens[3].type, Lexer.ITEM)
        self.assertEqual(tokens[3].name, 'request')
        self.assertEqual(tokens[3].value, 'GET /')

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

        self.assertEqual(tokens[2].lineno, 4)
        self.assertEqual(tokens[2].type, Lexer.ITEM)
        self.assertEqual(tokens[2].name, 'response_body')
        self.assertEqual(tokens[2].value, 'hello')

        self.assertEqual(tokens[5].lineno, 11)
        self.assertEqual(tokens[5].type, Lexer.ITEM)
        self.assertEqual(tokens[5].name, 'response_body')
        self.assertEqual(tokens[5].value, 'world')

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

        self.assertEqual(tokens[3].lineno, 7)
        self.assertEqual(tokens[3].type, Lexer.ITEM)
        self.assertEqual(tokens[3].name, 'response_body')
        self.assertEqual(tokens[3].value, '''
hello

''')

    @get_cases()
    @get_tokens()
    def test_case_10(self, tokens=None, preamble=None, cases=None):
        '''
# this is a comment
=== TEST 1.1: sanity 1
--- request eval: GET /

=== TEST 1.2: sanity 2
// this is a comment
# this is a comment too
--- request eval: GET /
'''
        self.assertEqual(len(tokens), 4)

        self.assertEqual(tokens[1].lineno, 4)

        self.assertEqual(tokens[3].lineno, 9)
        self.assertEqual(tokens[3].type, Lexer.ITEM)
        self.assertEqual(tokens[3].name, 'request')
        self.assertEqual(tokens[3].value, 'GET /')

        self.assertEqual(preamble, None)
        self.assertEqual(len(cases), 2)

        self.assertEqual(len(cases[0].items), 1)
        self.assertEqual(cases[0].name, 'TEST 1.1: sanity 1')

        self.assertEqual(len(cases[1].items), 1)
        self.assertEqual(cases[1].name, 'TEST 1.2: sanity 2')

    @get_cases()
    @get_tokens()
    def test_case_11(self, tokens=None, preamble=None, cases=None):
        '''
import sys

__DATA__
=== TEST 1: sanity

--- http_config
gzip on;

--- request
GET /
--- response_body like
^Hello [a-z]$

--- request
GET /
--- response_body eval like
r"^Hello [a-z]$"

=== TEST 2:
--- request eval: GET /
'''

        self.assertEqual(len(tokens), 9)

        self.assertEqual(tokens[4].lineno, 12)
        self.assertEqual(tokens[4].type, Lexer.ITEM)
        self.assertEqual(tokens[4].name, 'response_body')
        self.assertEqual(tokens[4].option, ['like'])
        self.assertEqual(tokens[4].value, '^Hello [a-z]$')

        self.assertEqual(tokens[6].name, 'response_body')
        self.assertEqual(tokens[6].option, ['eval', 'like'])

        self.assertEqual(tokens[7].lineno, 20)
        self.assertEqual(tokens[7].type, Lexer.CASE_LINE)
        self.assertEqual(tokens[7].name, 'TEST 2:')
        self.assertEqual(tokens[7].value, None)

        self.assertEqual(preamble.strip(), 'import sys')
        self.assertEqual(len(cases), 2)

        self.assertEqual(len(cases[0].items), 5)
        self.assertEqual(cases[0].name, 'TEST 1: sanity')

        self.assertEqual(len(cases[1].items), 1)
        self.assertEqual(cases[1].name, 'TEST 2:')

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

        self.assertEqual(tokens[3].lineno, 10)
        self.assertEqual(tokens[3].type, Lexer.ITEM)
        self.assertEqual(tokens[3].name, 'server_config')
        self.assertEqual(tokens[3].value, None)

        self.assertEqual(tokens[5].lineno, 13)
        self.assertEqual(tokens[5].type, Lexer.ITEM)
        self.assertEqual(tokens[5].name, 'response_body_like')
        self.assertEqual(tokens[5].value, '^Hello')

        self.assertEqual(tokens[6].lineno, 15)
        self.assertEqual(tokens[6].type, Lexer.ITEM)
        self.assertEqual(tokens[6].name, 'error_code')
        self.assertEqual(tokens[6].value, None)

    @get_tokens()
    def test_case_13(self, tokens=None):
        '''
import sys

__DATA__

=== TEST 1: sanity
--- http_config
# this is a comment
```
gzip on;
```
--- request
--- response_body_like eval
~~~"""
--- request"""~~~
--- error_code
'''

        self.assertEqual(len(tokens), 6)

        self.assertEqual(tokens[2].lineno, 7)
        self.assertEqual(tokens[2].type, Lexer.ITEM)
        self.assertEqual(tokens[2].name, 'http_config')
        self.assertEqual(tokens[2].value.strip(), 'gzip on;')

        self.assertEqual(tokens[4].lineno, 13)
        self.assertEqual(tokens[4].type, Lexer.ITEM)
        self.assertEqual(tokens[4].name, 'response_body_like')
        self.assertEqual(tokens[4].option, ['eval'])
        self.assertEqual(tokens[4].value, '''"""
--- request"""''')

    @get_tokens()
    def test_delimiter_00(self, tokens=None):
        '''
--- config
__EOF__

--- response_body
hello
__EOF__ world
__EOF__
'''

        self.assertEqual(len(tokens), 2)

        self.assertEqual(tokens[0].lineno, 2)
        self.assertEqual(tokens[0].type, Lexer.ITEM)
        self.assertEqual(tokens[0].name, 'config')
        self.assertEqual(tokens[0].value, '')

        self.assertEqual(tokens[1].lineno, 5)
        self.assertEqual(tokens[1].type, Lexer.ITEM)
        self.assertEqual(tokens[1].name, 'response_body')
        self.assertEqual(tokens[1].value, '''hello
__EOF__ world
''')

    @get_tokens()
    def test_delimiter_01(self, tokens=None):
        '''
--- config
 __EOF__
'''

        self.assertEqual(len(tokens), 1)

        self.assertEqual(tokens[0].lineno, 2)
        self.assertEqual(tokens[0].type, Lexer.ITEM)
        self.assertEqual(tokens[0].name, 'config')
        self.assertEqual(tokens[0].value, ' ')

    @get_tokens()
    def test_delimiter_02(self, tokens=None):
        '''
--- config

__EOF__

--- request
GET /
'''

        self.assertEqual(len(tokens), 2)

        self.assertEqual(tokens[0].lineno, 2)
        self.assertEqual(tokens[0].type, Lexer.ITEM)
        self.assertEqual(tokens[0].name, 'config')
        self.assertEqual(tokens[0].value, '')

        self.assertEqual(tokens[1].lineno, 6)
        self.assertEqual(tokens[1].type, Lexer.ITEM)
        self.assertEqual(tokens[1].name, 'request')
        self.assertEqual(tokens[1].value, 'GET /')

    @get_tokens()
    def test_string_block_00(self, tokens=None):
        '''
=== TEST 1: sanity
--- request eval
~~~
```
GET ''.join(['1'*1, '2*2, '3'*3])
```
~~~
'''

        self.assertEqual(len(tokens), 2)

        self.assertEqual(tokens[1].lineno, 3)
        self.assertEqual(tokens[1].type, Lexer.ITEM)
        self.assertEqual(tokens[1].name, 'request')
        self.assertEqual(tokens[1].option, ['eval'])
        self.assertEqual(tokens[1].value, '''
```
GET ''.join(['1'*1, '2*2, '3'*3])
```
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

        self.assertEqual(tokens[1].lineno, 3)
        self.assertEqual(tokens[1].type, Lexer.ITEM)
        self.assertEqual(tokens[1].name, 'request')
        self.assertEqual(tokens[1].option, ['eval'])
        self.assertEqual(tokens[1].value, '''"""
GET ''.join(['/', '1'*1, '2'*2, '3'*3])
"""''')

    @get_tokens()
    def test_string_block_02(self, tokens=None):
        '''
=== TEST 1: sanity
--- request eval
"""
GET ''.join(['/', '1'*1, '2'*2, '3'*3])
"""
'''

        self.assertEqual(len(tokens), 2)

        self.assertEqual(tokens[1].lineno, 3)
        self.assertEqual(tokens[1].type, Lexer.ITEM)
        self.assertEqual(tokens[1].name, 'request')
        self.assertEqual(tokens[1].option, ['eval'])
        self.assertEqual(tokens[1].value, '''"""
GET ''.join(['/', '1'*1, '2'*2, '3'*3])
"""''')

    @get_tokens()
    def test_comment_00(self, tokens=None):
        '''
=== TEST 1: sanity
--- request eval
// this is a comment
"""
GET /
"""
'''

        self.assertEqual(len(tokens), 2)

        self.assertEqual(tokens[1].lineno, 3)
        self.assertEqual(tokens[1].type, Lexer.ITEM)
        self.assertEqual(tokens[1].name, 'request')
        self.assertEqual(tokens[1].option, ['eval'])
        self.assertEqual(tokens[1].value, '''"""
GET /
"""''')

    @get_tokens()
    def test_comment_01(self, tokens=None):
        '''
# sanity test
=== TEST 1: sanity
--- request eval
GET /
// this is a comment
'''

        self.assertEqual(len(tokens), 2)

        self.assertEqual(tokens[1].lineno, 4)
        self.assertEqual(tokens[1].type, Lexer.ITEM)
        self.assertEqual(tokens[1].name, 'request')
        self.assertEqual(tokens[1].option, ['eval'])
        self.assertEqual(tokens[1].value, 'GET /')

    @get_tokens()
    def test_comment_02(self, tokens=None):
        '''
__DATA__
# sanity test
=== TEST 1: sanity
--- request eval
GET /
// this is a comment
'''

        self.assertEqual(len(tokens), 3)

        self.assertEqual(tokens[2].lineno, 5)
        self.assertEqual(tokens[2].type, Lexer.ITEM)
        self.assertEqual(tokens[2].name, 'request')
        self.assertEqual(tokens[2].option, ['eval'])
        self.assertEqual(tokens[2].value, 'GET /')

    @get_tokens(raises=LexException, raises_regexp='unexpected block: 1')
    def test_lex_exception_00(self, tokens=None):
        '''
import sys

__DATA__

1'''

    @get_tokens(raises=LexException,
                raises_regexp='unexpected string: ```1```')
    def test_lex_exception_01(self, tokens=None):
        '''
import sys

__DATA__

```1```
'''

    @get_tokens(raises=LexException,
                raises_regexp='unexpected block: 1')
    def test_lex_exception_02(self, tokens=None):
        '''
import sys

__DATA__

--- request
```
```
1
```
'''

    @get_tokens(raises=LexException,
                raises_regexp='unexpected block: __EOF__')
    def test_lex_exception_03(self, tokens=None):
        '''
import sys

__DATA__

--- request
__EOF__
__EOF__
'''

if __name__ == '__main__':
    unittest.main()
