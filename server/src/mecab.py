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
from re import DOTALL

### Constants
# TODO: EXTERNAL_DIR_PATH really should be specified elsewhere
EXTERNAL_DIR_PATH = path_join(dirname(__file__), '..', '..', 'external')
MECAB_PYTHON_PATH = path_join(EXTERNAL_DIR_PATH, 'mecab-python-0.98')

WAKATI_REGEX = re_compile(r'(\S.*?)(?:(?:(?<!\s)\s|$))', DOTALL)
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

    # Remember to decode or you WILL get the number of bytes
    parse = parse.decode('utf-8')

    # Wakati inserts spaces, but only after non-space tokens.
    # We find these iteratively and then allow additional spaces to be treated
    # as seperate tokens.

    # XXX: MeCab rapes newlines by removing them, we need to align ourselves
    last_end = 0
    for tok in (m.group(1) for m in WAKATI_REGEX.finditer(parse)):
        start = text.find(tok, last_end)
        end = start + len(tok)
        yield [start, end]
        last_end = end

if __name__ == '__main__':
    # Minor test: Is it a duck? Maybe?
    sentence = u'鴨かも？'
    token_offsets = [t for t in token_offsets_gen(sentence)]
    segmented = [sentence[start:end + 1] for start, end in token_offsets]
    print '\t'.join((sentence, unicode(token_offsets), '|'.join(segmented)))
