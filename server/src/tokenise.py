#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import with_statement

'''
Tokenisation using external software.

Author:     Pontus Stenetorp <pontus stenetorp se>
Version:    2011-05-23
'''

from os.path import join as path_join
from os.path import dirname
from subprocess import Popen, PIPE
from shlex import split as shlex_split

### Constants
EN_TOKENIZATION = "internal" # alternatives internal/external/simple
GTB_TOKENIZE_PL_PATH = path_join(dirname(__file__), '../../external/',
        'GTB-tokenize.pl')
###

try:
    from config import TOKENIZATION, WHITESPACE_TOKENIZATION, PTBLIKE_TOKENIZATION, JAPANESE_TOKENIZATION
except ImportError:
    WHITESPACE_TOKENIZATION, PTBLIKE_TOKENIZATION, JAPANESE_TOKENIZATION = range(3)
    TOKENIZATION = None

def _token_boundaries_by_alignment(tokens, original_text):
    curr_pos = 0
    for tok in tokens:
        start_pos = original_text.index(tok, curr_pos)
        # TODO: Check if we fail to find the token!
        end_pos = start_pos + len(tok)
        yield (start_pos, end_pos)
        curr_pos = end_pos

def jp_token_boundary_gen(text):
    # TODO: consider honoring WHITESPACE_TOKENIZATION for japanese also
    if TOKENIZATION is not None and TOKENIZATION != JAPANESE_TOKENIZATION:
        from message import Messager
        Messager.warning("Ignoring unexpected TOKENIZATION specification for Japanese.")
    from mecab import token_offsets_gen
    for o in token_offsets_gen(text):
        yield o

def en_token_boundary_gen_external(text):
    # Call the external script
    tok_p = Popen(shlex_split(GTB_TOKENIZE_PL_PATH), stdin=PIPE,
            stdout=PIPE, stderr=PIPE)

    tok_p.stdin.write(text.encode('utf-8'))
    tok_p.stdin.close()
    tok_p.wait()
    output, errors = (tok_p.stdout.read().decode('utf-8'),
            tok_p.stderr.read().decode('utf-8'))
    #output, errors = tok_p.communicate(text)

    # TODO: Check errors!

    # Decode our output, we assume utf-8 as this is our internal format
    #output = output.decode('utf-8')

    # Then align the now tokenised data to get the offsets
    tokens = output.split()
    for o in _token_boundaries_by_alignment(tokens, text):
        yield o

def en_token_boundary_gen_internal(text):
    from gtbtokenize import tokenize
    tokens = tokenize(text).split()
    for o in _token_boundaries_by_alignment(tokens, text):
        yield o

def en_token_boundary_gen_simple(text):
    tokens = text.split()
    for o in _token_boundaries_by_alignment(tokens, text):
        yield o

def en_token_boundary_gen(text):
    if TOKENIZATION is None or TOKENIZATION == WHITESPACE_TOKENIZATION:
        return en_token_boundary_gen_simple(text)        
    elif TOKENIZATION == PTBLIKE_TOKENIZATION:
        if EN_TOKENIZATION == "external":
            return en_token_boundary_gen_external(text)
        elif EN_TOKENIZATION == "internal":
            return en_token_boundary_gen_internal(text)
    else:
        from message import Messager
        Messager.warning("Unrecognized Engligh tokenization options for English, reverting to simple tokenization.")
        return en_token_boundary_gen_simple(text)

if __name__ == '__main__':
    from sys import argv

    from annotation import open_textfile

    def _text_by_offsets_gen(text, offsets):
        for start, end in offsets:
            yield text[start:end]

    try:
        for txt_file_path in argv[1:]:
            print
            print '### Tokenising:', txt_file_path
            with open_textfile(txt_file_path, 'r') as txt_file:
                text = txt_file.read()
            print '# Original text:'
            print text.replace('\n', '\\n')
            #offsets = [o for o in jp_token_boundary_gen(text)]
            offsets = [o for o in en_token_boundary_gen(text)]
            print '# Offsets:'
            print offsets
            print '# Tokens:'
            for tok in _text_by_offsets_gen(text, offsets):
                assert tok, 'blank tokens disallowed'
                assert not tok[0].isspace() and not tok[-1].isspace(), (
                        'tokens may not start or end with white-space "%s"' % tok)
                print '"%s"' % tok
    except IOError:
        pass # Most likely a broken pipe
