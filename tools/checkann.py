#!/usr/bin/env python

# Check that text-bound annotations in .ann file align with the
# corresponding .txt file.

import codecs
import re
import sys
from collections import namedtuple
from os.path import basename

Textbound = namedtuple('Textbound', 'id type start end text')

TEXTBOUND_RE = re.compile(r'^([A-Z]\d+)\t(\S+) (\d+) (\d+)\t(.*)$')


class FormatError(Exception):
    pass


def txt_for_ann(fn):
    tfn = re.sub(r'\.ann$', '.txt', fn)
    if tfn == fn:
        raise FormatError
    return tfn


def parse_textbound(s):
    m = TEXTBOUND_RE.match(s)
    if not m:
        raise FormatError
    id_, type_, start, end, text = m.groups()
    start, end = int(start), int(end)
    return Textbound(id_, type_, start, end, text)


def process(fn):
    textbounds = []

    with codecs.open(fn, 'rU', encoding='utf8', errors='strict') as f:
        for l in f:
            l = l.rstrip('\n')

            if not l or l.isspace():
                continue

            if l[0] != 'T':
                continue  # assume not a textbound annotation
            else:
                textbounds.append(parse_textbound(l))

    # debugging
#    print >> sys.stderr, '%s: %d textbounds' % (basename(fn), len(textbounds))

    with codecs.open(txt_for_ann(fn), 'rU', encoding='utf8',
                     errors='strict') as f:
        text = f.read()

    for id_, type_, start, end, ttext in textbounds:
        try:
            assert text[start:end] == ttext
        except BaseException:
            print('Mismatch in %s: %s %d %d' % (basename(fn), id_, start, end))
            print('     reference: %s' % \
                ttext.encode('utf-8').replace('\n', '\\n'))
            print('     document : %s' % \
                text[start:end].encode('utf-8').replace('\n', '\\n'))


def main(argv=None):
    if argv is None:
        argv = sys.argv

    if len(argv) < 2:
        print('Usage:', argv[0], 'FILE [FILE [...]]', file=sys.stderr)
        return 1

    for fn in argv[1:]:
        process(fn)

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
