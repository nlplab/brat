#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

# Implements a GENIA Treebank - like tokenization. 

# This is a python translation of my GTB-tokenize.pl, which in turn
# draws in part on Robert MacIntyre's 1995 PTB tokenizer,
# (http://www.cis.upenn.edu/~treebank/tokenizer.sed) and Yoshimasa
# Tsuruoka's GENIA tagger tokenization (tokenize.cpp;
# www-tsujii.is.s.u-tokyo.ac.jp/GENIA/tagger)

# by Sampo Pyysalo, 2011. Licensed under the MIT license.
# http://www.opensource.org/licenses/mit-license.php

# NOTE: intended differences to GTB tokenization:
# - Does not break "protein(s)" -> "protein ( s )"

from __future__ import with_statement

import re

INPUT_ENCODING = "UTF-8"
OUTPUT_ENCODING = "UTF-8"
DEBUG_GTB_TOKENIZATION = False

# Penn treebank bracket escapes (others excluded)
PTB_ESCAPES = [('(', '-LRB-'),
               (')', '-RRB-'),
               ('[', '-LSB-'),
               (']', '-RSB-'),
               ('{', '-LCB-'),
               ('}', '-RCB-'),
               ]

def PTB_escape(s):
    for u, e in PTB_ESCAPES:
        s = s.replace(u, e)
    return s

def PTB_unescape(s):
    for u, e in PTB_ESCAPES:
        s = s.replace(e, u)
    return s

# processing in three stages: "initial" regexs run first, then
# "repeated" run as long as there are changes, and then "final"
# run. As the tokenize() function itself is trivial, comments relating
# to regexes given with the re.compiles.

__initial, __repeated, __final = [], [], []

# separate but do not break ellipsis
__initial.append((re.compile(r'\.\.\.'), r' ... '))

# To avoid breaking names of chemicals, protein complexes and similar,
# only add space to related special chars if there's already space on
# at least one side.
__initial.append((re.compile(r'([,;:@#]) '), r' \1 '))
__initial.append((re.compile(r' ([,;:@#])'), r' \1 '))

# always separated
__initial.append((re.compile(r'\$'), r' $ '))
__initial.append((re.compile(r'\%'), r' % '))
__initial.append((re.compile(r'\&'), r' & '))

# separate punctuation followed by space even if there's closing
# brackets or quotes in between, but only sentence-final for
# periods (don't break e.g. "E. coli").
__initial.append((re.compile(r'([,:;])([\[\]\)\}\>\"\']* +)'), r' \1\2'))
__initial.append((re.compile(r'(\.+)([\[\]\)\}\>\"\']* +)$'), r' \1\2'))

# these always
__initial.append((re.compile(r'\?'), ' ? '))
__initial.append((re.compile(r'\!'), ' ! '))

# separate greater than and less than signs, avoiding breaking
# "arrows" (e.g. "-->", ">>") and compound operators (e.g. "</=")
__initial.append((re.compile(r'((?:=\/)?<+(?:\/=|--+>?)?)'), r' \1 '))
__initial.append((re.compile(r'((?:<?--+|=\/)?>+(?:\/=)?)'), r' \1 '))

# separate dashes, not breaking up "arrows"
__initial.append((re.compile(r'(<?--+\>?)'), r' \1 '))

# Parens only separated when there's space around a balanced
# bracketing. This aims to avoid splitting e.g. beta-(1,3)-glucan,
# CD34(+), CD8(-)CD3(-).

# Previously had a proper recursive implementation for this, but it
# was much too slow for large-scale use. The following is
# comparatively fast but a bit of a hack:

# First "protect" token-internal brackets by replacing them with
# their PTB escapes. "Token-internal" brackets are defined as
# matching brackets of which at least one has no space on either
# side. To match GTB tokenization for cases like "interleukin
# (IL)-mediated", and "p65(RelA)/p50", treat following dashes and
# slashes as space.  Nested brackets are resolved inside-out;
# to get this right, add a heuristic considering boundary
# brackets as "space".

# (First a special case (rareish): "protect" cases with dashes after
# paranthesized expressions that cannot be abbreviations to avoid
# breaking up e.g. "(+)-pentazocine". Here, "cannot be abbreviations"
# is taken as "contains no uppercase charater".)
__initial.append((re.compile(r'\(([^ A-Z()\[\]{}]+)\)-'), r'-LRB-\1-RRB--'))

# These are repeated until there's no more change (per above comment)
__repeated.append((re.compile(r'(?<![ (\[{])\(([^ ()\[\]{}]*)\)'), r'-LRB-\1-RRB-'))
__repeated.append((re.compile(r'\(([^ ()\[\]{}]*)\)(?![ )\]}\/-])'), r'-LRB-\1-RRB-'))
__repeated.append((re.compile(r'(?<![ (\[{])\[([^ ()\[\]{}]*)\]'), r'-LSB-\1-RSB-'))
__repeated.append((re.compile(r'\[([^ ()\[\]{}]*)\](?![ )\]}\/-])'), r'-LSB-\1-RSB-'))
__repeated.append((re.compile(r'(?<![ (\[{])\{([^ ()\[\]{}]*)\}'), r'-LCB-\1-RCB-'))
__repeated.append((re.compile(r'\{([^ ()\[\]{}]*)\}(?![ )\]}\/-])'), r'-LCB-\1-RCB-'))

# Remaining brackets are not token-internal and should be
# separated.
__final.append((re.compile(r'\('), r' -LRB- '))
__final.append((re.compile(r'\)'), r' -RRB- '))
__final.append((re.compile(r'\['), r' -LSB- '))
__final.append((re.compile(r'\]'), r' -RSB- '))
__final.append((re.compile(r'\{'), r' -LCB- '))
__final.append((re.compile(r'\}'), r' -RCB- '))

# initial single quotes always separated
__final.append((re.compile(r' (\'+)'), r' \1 '))
# final with the exception of 3' and 5' (rough heuristic)
__final.append((re.compile(r'(?<![35\'])(\'+) '), r' \1 '))

# This more frequently disagreed than agreed with GTB
#     # Separate slashes preceded by space (can arise from
#     # e.g. splitting "p65(RelA)/p50"
#     __final.append((re.compile(r' \/'), r' \/ '))

# Standard from PTB (TODO: pack)
__final.append((re.compile(r'\'s '), ' \'s '))
__final.append((re.compile(r'\'S '), ' \'S '))
__final.append((re.compile(r'\'m '), ' \'m '))
__final.append((re.compile(r'\'M '), ' \'M '))
__final.append((re.compile(r'\'d '), ' \'d '))
__final.append((re.compile(r'\'D '), ' \'D '))
__final.append((re.compile(r'\'ll '), ' \'ll '))
__final.append((re.compile(r'\'re '), ' \'re '))
__final.append((re.compile(r'\'ve '), ' \'ve '))
__final.append((re.compile(r'n\'t '), ' n\'t '))
__final.append((re.compile(r'\'LL '), ' \'LL '))
__final.append((re.compile(r'\'RE '), ' \'RE '))
__final.append((re.compile(r'\'VE '), ' \'VE '))
__final.append((re.compile(r'N\'T '), ' N\'T '))

__final.append((re.compile(r' Cannot '), ' Can not '))
__final.append((re.compile(r' cannot '), ' can not '))
__final.append((re.compile(r' D\'ye '), ' D\' ye '))
__final.append((re.compile(r' d\'ye '), ' d\' ye '))
__final.append((re.compile(r' Gimme '), ' Gim me '))
__final.append((re.compile(r' gimme '), ' gim me '))
__final.append((re.compile(r' Gonna '), ' Gon na '))
__final.append((re.compile(r' gonna '), ' gon na '))
__final.append((re.compile(r' Gotta '), ' Got ta '))
__final.append((re.compile(r' gotta '), ' got ta '))
__final.append((re.compile(r' Lemme '), ' Lem me '))
__final.append((re.compile(r' lemme '), ' lem me '))
__final.append((re.compile(r' More\'n '), ' More \'n '))
__final.append((re.compile(r' more\'n '), ' more \'n '))
__final.append((re.compile(r'\'Tis '), ' \'T is '))
__final.append((re.compile(r'\'tis '), ' \'t is '))
__final.append((re.compile(r'\'Twas '), ' \'T was '))
__final.append((re.compile(r'\'twas '), ' \'t was '))
__final.append((re.compile(r' Wanna '), ' Wan na '))
__final.append((re.compile(r' wanna '), ' wan na '))

# clean up possible extra space
__final.append((re.compile(r'  +'), r' '))

def _tokenize(s):
    """
    Tokenizer core. Performs GTP-like tokenization, using PTB escapes
    for brackets (but not quotes). Assumes given string has initial
    and terminating space. You probably want to use tokenize() instead
    of this function.
    """

    # see re.complies for comments
    for r, t in __initial:
        s = r.sub(t, s)

    while True:
        o = s
        for r, t in __repeated:
            s = r.sub(t, s)
        if o == s: break

    for r, t in __final:
        s = r.sub(t, s)

    return s

def tokenize(s, ptb_escaping=False, use_single_quotes_only=False,
             escape_token_internal_parens=False):
    """
    Tokenizes the given string with a GTB-like tokenization. Input
    will adjusted by removing surrounding space, if any. Arguments
    hopefully self-explanatory.
    """

    if DEBUG_GTB_TOKENIZATION:
        orig = s

    # Core tokenization needs starting and ending space and no newline;
    # store to return string ending similarly
    # TODO: this isn't this difficult ... rewrite nicely
    s = re.sub(r'^', ' ', s)
    m = re.match(r'^((?:.+|\n)*?) *(\n*)$', s)
    assert m, "INTERNAL ERROR on '%s'" % s # should always match
    s, s_end = m.groups()    
    s = re.sub(r'$', ' ', s)

    if ptb_escaping:
        if use_single_quotes_only:
            # special case for McCCJ: escape into single quotes. 
            s = re.sub(r'([ \(\[\{\<])\"', r'\1 '+"' ", s)
        else:
            # standard PTB quote escaping
            s = re.sub(r'([ \(\[\{\<])\"', r'\1 `` ', s)
    else:
        # no escaping, just separate
        s = re.sub(r'([ \(\[\{\<])\"', r'\1 " ', s)

    s = _tokenize(s)

    # as above (not quite sure why this is after primary tokenization...)
    if ptb_escaping:
        if use_single_quotes_only:
            s = s.replace('"', " ' ")
        else:
            s = s.replace('"', " '' ")
    else:
        s = s.replace('"', ' " ')

    if not ptb_escaping:
        if not escape_token_internal_parens:
            # standard unescape for PTB escapes introduced in core
            # tokenization
            s = PTB_unescape(s)
        else:
            # only unescape if a space can be matched on both
            # sides of the bracket.
            s = re.sub(r'(?<= )-LRB-(?= )', '(', s)
            s = re.sub(r'(?<= )-RRB-(?= )', ')', s)
            s = re.sub(r'(?<= )-LSB-(?= )', '[', s)
            s = re.sub(r'(?<= )-RSB-(?= )', ']', s)
            s = re.sub(r'(?<= )-LCB-(?= )', '{', s)
            s = re.sub(r'(?<= )-RCB-(?= )', '}', s)

    # Clean up added space (well, maybe other also)
    s = re.sub(r'  +', ' ', s)
    s = re.sub(r'^ +', '', s)
    s = re.sub(r' +$', '', s)

    # Only do final comparison in debug mode.
    if DEBUG_GTB_TOKENIZATION:
        # revised must match original when whitespace, quotes (etc.)
        # and escapes are ignored
        # TODO: clean this up
        r1 = PTB_unescape(orig.replace(' ', '').replace('\n','').replace("'",'').replace('"','').replace('``',''))
        r2 = PTB_unescape(s.replace(' ', '').replace('\n','').replace("'",'').replace('"','').replace('``',''))
        if r1 != r2:
            print >> sys.stderr, "tokenize(): error: text mismatch (returning original):\nORIG: '%s'\nNEW:  '%s'" % (orig, s)
            s = orig

    return s+s_end

def __argparser():
    import argparse

    ap=argparse.ArgumentParser(description="Perform GENIA Treebank-like text tokenization.")
    ap.add_argument("-ptb", default=False, action="store_true", help="Use Penn Treebank escapes")
    ap.add_argument("-mccc", default=False, action="store_true", help="Special processing for McClosky-Charniak-Johnson parser input")
    ap.add_argument("-sp", default=False, action="store_true", help="Special processing for Stanford parser+PTBEscapingProcessor input. (not necessary for Stanford Parser version 1.6.5 and newer)")
    ap.add_argument("files", metavar="FILE", nargs="*", help="Files to tokenize.")
    return ap


def main(argv):
    import sys
    import codecs

    arg = __argparser().parse_args(argv[1:])

    # sorry, the special cases are a bit of a mess
    ptb_escaping, use_single_quotes_only, escape_token_internal_parens = False, False, False
    if arg.ptb: 
        ptb_escaping = True
    if arg.mccc:
        ptb_escaping = True 
        # current version of McCCJ has trouble with double quotes
        use_single_quotes_only = True
    if arg.sp:
        # current version of Stanford parser PTBEscapingProcessor
        # doesn't correctly escape word-internal parentheses
        escape_token_internal_parens = True
    
    # for testing, read stdin if no args
    if len(arg.files) == 0:
        arg.files.append('/dev/stdin')

    for fn in arg.files:
        try:
            with codecs.open(fn, encoding=INPUT_ENCODING) as f:
                for l in f:
                    t = tokenize(l, ptb_escaping=ptb_escaping,
                                 use_single_quotes_only=use_single_quotes_only,
                                 escape_token_internal_parens=escape_token_internal_parens)
                    sys.stdout.write(t.encode(OUTPUT_ENCODING))
        except Exception, e:
            print >> sys.stderr, "Failed to read", fn, ":", e
            
if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
