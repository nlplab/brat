#!/usr/bin/env python
# -*- coding: utf-8 -*-`

'''
MeCab wrapper for brat

http://mecab.sourceforge.net/

Author:     Pontus Stenetorp <pontus stenetorp se>
Version:    2011-05-17
'''

from os.path import dirname
from os.path import join as path_join
from re import compile as re_compile

### Constants
# TODO: EXTERNAL_DIR_PATH really should be specified elsewhere
EXTERNAL_DIR_PATH = path_join(dirname(__file__), '..', '..', 'external')
MECAB_PYTHON_PATH = path_join(EXTERNAL_DIR_PATH, 'mecab-python-0.98')

WAKATI_FIRST_PASS_REGEX = re_compile(r'(.*?)(?:(?<!\s)\s)')
###

try:
    import MeCab as mecab
except ImportError:
    # We probably haven't added the path yet
    from sys import path as sys_path
    sys_path.append(MECAB_PYTHON_PATH)
    import MeCab as mecab

# Boundaries are on the form: [start, end]
def token_offsets_gen(text):
    # Parse in Wakati format
    tagger = mecab.Tagger('-O wakati')

    # Parse into Wakati format, MeCab only takes utf-8
    parse = tagger.parse(text.encode('utf-8'))

    # Wakati inserts spaces, but only after non-space tokens.
    # We find these iteratively and then allow additional spaces to be treated
    # as seperate tokens.
    last_end = 0
    for tok in (m.group(1) for m in WAKATI_FIRST_PASS_REGEX.finditer(parse)):
        # Remember to decode or you WILL get the number of bytes
        tok_len = len(tok.decode('utf-8'))
        yield [last_end, last_end + tok_len - 1]
        last_end += tok_len

if __name__ == '__main__':
    # Minor test: Is it a duck? Maybe?
    sentence = u'鴨かも？'
    token_offsets = [t for t in token_offsets_gen(sentence)]
    segmented = [sentence[start:end + 1] for start, end in token_offsets]
    print '\t'.join((sentence, unicode(token_offsets), '|'.join(segmented)))
