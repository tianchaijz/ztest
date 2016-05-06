" Vim syntax file
" Language:    ztest
" Maintainer:  Jinzheng Zhang <tianchaijz@gmail.com>


if exists('b:current_syntax') && b:current_syntax == 'ztest'
    finish
endif


syn keyword pythonStatement    as assert break continue del exec global
syn keyword pythonStatement    lambda nonlocal pass print return with yield
syn keyword pythonStatement    class def nextgroup=pythonFunction skipwhite
syn keyword pythonConditional  elif else if
syn keyword pythonRepeat       for while
syn keyword pythonOperator     and in is not or
syn keyword pythonException    except finally raise try
syn keyword pythonInclude      from import

syn keyword pythonBuiltin  False True None
syn keyword pythonBuiltin  NotImplemented Ellipsis __debug__
syn keyword pythonBuiltin  abs all any bin bool chr classmethod
syn keyword pythonBuiltin  compile complex delattr dict dir divmod
syn keyword pythonBuiltin  enumerate eval filter float format
syn keyword pythonBuiltin  frozenset getattr globals hasattr hash
syn keyword pythonBuiltin  hex id input int isinstance
syn keyword pythonBuiltin  issubclass iter len list locals map max
syn keyword pythonBuiltin  min next object oct open ord pow print
syn keyword pythonBuiltin  property range repr reversed round set
syn keyword pythonBuiltin  setattr slice sorted staticmethod str
syn keyword pythonBuiltin  sum super tuple type vars zip __import__
syn keyword pythonBuiltin  basestring callable cmp execfile file
syn keyword pythonBuiltin  long raw_input reduce reload unichr
syn keyword pythonBuiltin  unicode xrange

syn region pythonString
    \ start=+[uU]\=\z(['"]\)+ end="\z1" skip="\\\\\|\\\z1"
syn region pythonString
    \ start=+[uU]\=\z('''\|"""\)+ end="\z1" keepend
syn region pythonRawString
    \ start=+[uU]\=[rR]\z(['"]\)+ end="\z1" skip="\\\\\|\\\z1"
syn region pythonRawString
    \ start=+[uU]\=[rR]\z('''\|"""\)+ end="\z1" keepend

syn match pythonFunction
    \ "\%(\%(def\s\|class\s\|@\)\s*\)\@<=\h\%(\w\|\.\)*" contained

syn keyword ztestTodo      contained TODO FIXME XXX NOTE
syn match   ztestComment   "^\s*//.*$" contains=ztestTodo
syn match   ztestComment   "\%^#!.*"
syn match   ztestCaseLine  "^===.*"
syn match   ztestItem      "^--- [a-z_]\+"

syn keyword ztestBool        false none true null nil on off
syn keyword ztestEof         __EOF__
syn keyword ztestItemOption  eval exec json yaml
syn keyword ztestOperator    and or not

syn region  ztestStringBlock
    \ start="\z\([`~,;%@><]\{3,}\)" end="\z1"
    \ contains=pythonBuiltin,pythonStatement,pythonConditional,pythonRepeat,
    \ pythonOperator,pythonException,pythonInclude,pythonFunction,pythonString,
    \ pythonRawString


hi def link pythonInclude      Include
hi def link pythonBuiltin      Function
hi def link pythonFunction     Function
hi def link pythonException    Exception
hi def link pythonConditional  Conditional
hi def link pythonRepeat       Repeat
hi def link pythonOperator     Operator
hi def link pythonString       String
hi def link pythonRawString    String

hi def link ztestTodo         Todo
hi def link ztestComment      Comment
hi def link ztestCaseLine     Structure
hi def link ztestStringBlock  String
hi def link ztestEof          Define
hi def link ztestBool         Boolean
hi def link ztestOperator     Operator
hi def link ztestItem         Statement
hi def link ztestItemName     Statement
hi def link ztestItemOption   Define


if !exists('b:current_syntax')
    let b:current_syntax = 'ztest'
endif
