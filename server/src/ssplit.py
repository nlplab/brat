#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
Python re-write of Sampo Pyysalo's GeniaSS sentence split refiner and some
convenience functions. Also a primitive Japanese sentence splitter.

Author:     Pontus Stenetorp <pontus stenetorp se>
Version:    2011-05-09
'''

from re import compile as re_compile
from re import DOTALL

### Constants
# Require a leading non-whitespace, end on delimiter and space
# or newline followed by non-whitespace
EN_SENTENCE_END_REGEX = re_compile(r'\S.*?(:?(?:\.|!|\?)(?=\s+)|(?=\n+\S))', DOTALL)
JP_SENTENCE_END_REGEX = re_compile(ur'\S.*?[。！？]+(:?(?![。！？])|(?=\n+\S))')

# From the GeniaSS refiner
QMARK_BREAK_REGEX = re_compile(r'\b([a-z]+\?) ([A-Z][a-z]+)\b')
# TODO: Shouldn't there be a + after the space?
DOT_BREAK_REGEX = re_compile(r'\b([a-z]+ \.) ([A-Z][a-z]+)\b')
###

# Mandatory Deep Purple refence: Pythonbringer by De-(Perl)ped
def _refine_split(sentences):
    raise NotImplementedError # TODO:
    for s in sentences:
        # Breaks are sometimes missing after question marks, "safe" cases
        s = QMARK_BREAK_REGEX.sub('\1\n\2', s)
        # Breaks are sometimes missing after dots, "safe" cases
        s = DOT_BREAK_REGEX.sub('\1\n\2', s)

        # No breaks producing lines only containing sentence-ending punctuation
        for ns in s.split('\n'):
            yield ns

# TODO: This could probably be turned into a nice regex, but we are in a hurry
def _sentence_boundary_gen(text, regex):
    for match in regex.finditer(text):
        yield match.span()
    raise StopIteration
    '''
    # XXX: OLD!
    last_end = 0
    # Find all sentence endings
    for match in regex.finditer(text):
        m_text = match.group()
        ls_text = m_text.lstrip()
        rs_text = m_text.rstrip()

        # Have we lost any size due to leading white space?
        if len(ls_text) != len(m_text):
            l_offset = len(m_text) - len(ls_text)
        else:
            l_offset = 0

        if len(rs_text) != len(m_text):
            r_offset = len(m_text) - len(rs_text)
        else:
            r_offset = 0

        start = last_end + l_offset
        end = start + len(m_text) - r_offset - l_offset

        yield (start, end)

        last_end = match.end()

    # Are there any non-space tokens left?
    m_text = text[last_end:]
    if m_text.strip():
        ls_text = m_text.lstrip()
        rs_text = m_text.rstrip()

        # Have we lost any size due to leading white space?
        if len(ls_text) != len(m_text):
            l_offset = len(m_text) - len(ls_text)
        else:
            l_offset = 0

        if len(rs_text) != len(m_text):
            r_offset = len(m_text) - len(rs_text)
        else:
            r_offset = 0

        start = last_end + l_offset
        end = start + len(m_text) - l_offset - r_offset

        yield (start, end)
    '''

def jp_sentence_boundary_gen(text):
    for o in _sentence_boundary_gen(text, JP_SENTENCE_END_REGEX):
        yield o
       
# TODO: The regular expression is too crude, plug in the refine
#       script as well so that we can have reasonable splits.
def en_sentence_boundary_gen(text):
    for o in _sentence_boundary_gen(text, EN_SENTENCE_END_REGEX):
        yield o

if __name__ == '__main__':
    from sys import argv

    from annotation import open_textfile

    def _text_by_offsets_gen(text, offsets):
        for start, end in offsets:
            yield text[start:end]

    if len(argv) > 1:
        try:
            for txt_file_path in argv[1:]:
                print
                print '### Splitting:', txt_file_path
                with open_textfile(txt_file_path, 'r') as txt_file:
                    text = txt_file.read()
                print '# Original text:'
                print text.replace('\n', '\\n')
                offsets = [o for o in jp_sentence_boundary_gen(text)]
                print '# Offsets:'
                print offsets
                print '# Sentences:'
                for sentence in _text_by_offsets_gen(text, offsets):
                    assert sentence, 'blank sentences disallowed'
                    assert not sentence[0].isspace(), (
                            'sentence may not start with white-space "%s"' % sentence)
                    print '"%s"' % sentence.replace('\n', '\\n')
        except IOError:
            pass # Most likely a broken pipe
    else:
        sentence = u'　変しん！　両になった。うそ！　かも　'
        print 'Sentence:', sentence
        print 'Len sentence:', len(sentence)

        ret = [o for o in jp_sentence_boundary_gen(sentence)]
        ans = [(1, 5), (6, 12), (12, 15), (16, 18)]
        assert ret == ans, '%s != %s' % (ret, ans)
        print 'Succesful!'

        sentence = ' One of these days Jimmy, one of these days. Boom! Kaboom '
        print 'Sentence:', sentence
        print 'Len sentence:', len(sentence)

        ret = [o for o in en_sentence_boundary_gen(sentence)]
        ans = [(1, 44), (45, 50), (51, 57)]
        assert ret == ans, '%s != %s' % (ret, ans)
        print 'Succesful!'

        with open('/home/ninjin/public_html/brat/brat_test_data/epi/PMID-18573876.txt', 'r') as _file:
            sentence = _file.read()

        print 'Sentence:', sentence
        print 'Len sentence:', len(sentence)

        ret = [o for o in en_sentence_boundary_gen(sentence)]
        last_end = 0
        for start, end in ret:
            if last_end != start:
                print 'DROPPED: "%s"' % sentence[last_end:start]
            print 'SENTENCE: "%s"' % sentence[start:end]
            last_end = end
        print ret
