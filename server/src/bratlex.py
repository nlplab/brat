#!/usr/bin/env python

'''
Tokenisation for the brat stand-off format:

https://github.com/TsujiiLaboratory/brat/wiki/Annotation-Data-Format

Author:  Pontus Stenetorp    <pontus stenetorp se>
Version: 2011-07-11
'''

# TODO: Require inital characters for ID;s for specific lines

try:
    import ply.lex as lex
except ImportError:
    # We need to add ply to path
    from sys import path as sys_path
    from os.path import join as path_join
    from os.path import dirname

    sys_path.append(path_join(dirname(__file__), '../lib/ply-3.4'))

    import ply.lex as lex

tokens = (
        # Primitives
        'COLON',
        'NEWLINE',
        'SPACE',
        'TAB',
        'WILDCARD',

        # Values
        'ID',
        'INTEGER',
        'TYPE',

        # Identifiers
        ''

        # Special-case for freetext
        'FREETEXT',
        )

states = (
        ('freetext', 'exclusive'),
        )

t_COLON     = r':'
t_SPACE     = r'\ '
t_WILDCARD  = r'\*'

def t_NEWLINE(t):
    r'\n'
    # Increment the lexers line-count
    t.lexer.lineno += 1
    # Reset the count of tabs on this line
    t.lexer.line_tab_count = 0
    return t

def t_TAB(t):
    r'\t'
    # Increment the number of tabs we have soon on this line
    t.lexer.line_tab_count += 1
    if t.lexer.line_tab_count == 2:
        t.lexer.begin('freetext')
    return t

def t_ID(t):
    r'(T|E|M|R|\#)[0-9]+'
    return t

def t_INTEGER(t):
    r'\d+'
    t.value = int(t.value) 
    return t

def t_TYPE(t):
    r'[A-Z][A-Za-z_-]*'
    return t

def t_freetext_FREETEXT(t):
    r'[^\n\t]+'
    return t

def t_freetext_TAB(t):
    r'\t'
    # End freetext mode INITAL
    t.lexer.begin('INITIAL')
    return t

def t_freetext_NEWLINE(t):
    r'\n'
    # Increment the lexers line-count
    t.lexer.lineno += 1
    # Reset the count of tabs on this line
    t.lexer.line_tab_count = 0
    # End freetext mode INITAL
    t.lexer.begin('INITIAL')
    return t

# Error handling rule
def t_error(t):
    print "Illegal character '%s'" % t.value[0]
    raise Exception
    t.lexer.skip(1)

def t_freetext_error(t):
    return t_error(t)

lexer = lex.lex()
lexer.line_tab_count = 0

if __name__ == '__main__':
    from sys import stdin
    for line in stdin:
        lexer.input(line)

        for tok in lexer:
            pass
            print tok
