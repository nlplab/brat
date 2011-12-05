#!/usr/bin/env python

'''
Grammar for the brat stand-off format.

Example, test grammar on a collection:

    find . -name '*.ann' | parallel cat | ./bratyacc.py

Author:   Pontus Stenetorp    <pontus stenetorp se>
Version:  2011-07-11
'''

try:
    import ply.yacc as yacc
except ImportError:
    # We need to add ply to path
    from sys import path as sys_path
    from os.path import join as path_join
    from os.path import dirname

    sys_path.append(path_join(dirname(__file__), '../lib/ply-3.4'))

    import ply.yacc as yacc

from bratlex import tokens

# TODO: Recurse all the way to a file
# TODO: Comment annotation

def p_annotation_line(p):
    '''
    annotation_line : annotation NEWLINE
    '''
    p[0] = '%s\n' % (p[1], )
    return p

# TODO: Ugly newline
def p_annotation(p):
    '''
    annotation  : textbound
                | event
                | modifier
                | equiv
                | relation
                | comment
    '''
    p[0] = p[1]
    return p

# TODO: What do we really call these?
def p_equiv(p):
    '''
    equiv : equiv_core SPACE equiv_members
    '''
    p[0] = '%s %s' % (p[1], p[3], )
    return p

def p_equiv_core(p):
    '''
    equiv_core : WILDCARD TAB TYPE
    '''
    p[0] = '*\t%s' % (p[3], )
    return p

def p_equiv_members(p):
    '''
    equiv_members   : equiv_member SPACE equiv_members
                    | equiv_member
    '''
    p[0] = '%s' % (p[1], )
    try:
        p[0] += ' %s' % (p[3], )
    except IndexError:
        # We did not have any more members
        pass
    return p

def p_equiv_member(p):
    '''
    equiv_member : id
    '''
    p[0] = '%s' % (p[1], )
    return p

def p_textbound(p):
    '''
    textbound   :  textbound_freetext
                |  textbound_core
    '''
    p[0] = p[1]
    return p

def p_textbound_core(p):
    '''
    textbound_core : TEXT_BOUND_ID TAB TYPE SPACE INTEGER SPACE INTEGER
    '''
    p[0] = '%s\t%s %d %d' % (p[1], p[3], p[5], p[7], )
    return p

def p_textbound_freetext(p):
    '''
    textbound_freetext : textbound_core TAB FREETEXT
    '''
    p[0] = '%s\t%s' % (p[1], p[3], )
    return p

def p_comment(p):
    '''
    comment : COMMENT_ID TAB TYPE SPACE id
    '''
    p[0] = '%s\t%s %s' % (p[1], p[3], p[5])
    return p

def p_event(p):
    '''
    event   : event_core SPACE event_arguments
            | event_core SPACE
            | event_core
    '''
    p[0] = p[1]
    try:
        p[0] += p[2]
    except IndexError:
        pass
    try:
        p[0] += p[3]
    except IndexError:
        pass
    return p

def p_event_core(p):
    '''
    event_core : EVENT_ID TAB TYPE COLON id
    '''
    p[0] = '%s\t%s:%s' % (p[1], p[3], p[5], )
    return p

def p_event_arguments(p):
    '''
    event_arguments : event_argument SPACE event_arguments
                    | event_argument
    '''
    p[0] = '%s' % (p[1], )
    try:
        p[0] += ' ' + p[3]
    except IndexError:
        pass
    return p

def p_event_argument(p):
    '''
    event_argument : argument COLON id
    '''
    p[0] = '%s:%s' % (p[1], p[3], )
    return p

def p_modifier(p):
    '''
    modifier : MODIFIER_ID TAB TYPE SPACE id
    '''
    p[0] = '%s\t%s %s' % (p[1], p[3], p[5], )
    return p

def p_relation(p):
    '''
    relation : RELATION_ID TAB TYPE SPACE argument COLON id SPACE argument COLON id
    '''
    # TODO: Should probably require only one of each argument type
    p[0] = '%s\t%s %s:%s %s:%s' % (p[1], p[3], p[5], p[7], p[9], p[11], )
    return p

def p_argument(p):
    '''
    argument    : TYPE
                | TYPE INTEGER
    '''
    p[0] = p[1]
    try:
        p[0] += str(p[2])
    except IndexError:
        pass
    return p

# Generic id
def p_id(p):
    '''
    id  : TEXT_BOUND_ID
        | EVENT_ID
        | RELATION_ID
        | MODIFIER_ID
        | COMMENT_ID
    '''
    p[0] = p[1]
    return p

def p_error(p):
    print 'Syntax error in input! "%s"'  % (str(p), )
    raise Exception

parser = yacc.yacc()

if __name__ == '__main__':
    from sys import stdin
    for line in stdin:
        print 'Input: "%s"' % line.rstrip('\n')
        result = parser.parse(line)
        assert result == line, ('"%s" != "%s"' % (result, line)
                ).replace('\n', '\\n')
        print result,
