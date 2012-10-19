#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import with_statement

'''
Tokenisation related functionality.

Author:     Pontus Stenetorp <pontus stenetorp se>
Version:    2011-05-23
'''

from os.path import join as path_join
from os.path import dirname
from subprocess import Popen, PIPE
from shlex import split as shlex_split

def _token_boundaries_by_alignment(tokens, original_text):
    curr_pos = 0
    for tok in tokens:
        start_pos = original_text.index(tok, curr_pos)
        # TODO: Check if we fail to find the token!
        end_pos = start_pos + len(tok)
        yield (start_pos, end_pos)
        curr_pos = end_pos

def jp_token_boundary_gen(text):
    from mecab import token_offsets_gen
    for o in token_offsets_gen(text):
        yield o

def gtb_token_boundary_gen(text):
    from gtbtokenize import tokenize
    tokens = tokenize(text).split()
    for o in _token_boundaries_by_alignment(tokens, text):
        yield o

def whitespace_token_boundary_gen(text):
    tokens = text.split()
    for o in _token_boundaries_by_alignment(tokens, text):
        yield o

if __name__ == '__main__':
    from sys import argv

    from annotation import open_textfile

    def _text_by_offsets_gen(text, offsets):
        for start, end in offsets:
            yield text[start:end]

    if len(argv) == 1:
        argv.append('/dev/stdin')

    try:
        for txt_file_path in argv[1:]:
            print
            print '### Tokenising:', txt_file_path
            with open(txt_file_path, 'r') as txt_file:
                text = txt_file.read()
                print text
            print '# Original text:'
            print text.replace('\n', '\\n')
            #offsets = [o for o in jp_token_boundary_gen(text)]
            #offsets = [o for o in whitespace_token_boundary_gen(text)]
            offsets = [o for o in gtb_token_boundary_gen(text)]
            print '# Offsets:'
            print offsets
            print '# Tokens:'
            for tok in _text_by_offsets_gen(text, offsets):
                assert tok, 'blank tokens disallowed'
                assert not tok[0].isspace() and not tok[-1].isspace(), (
                        'tokens may not start or end with white-space "%s"' % tok)
                print '"%s"' % tok
    except IOError:
        raise
