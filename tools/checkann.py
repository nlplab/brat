#!/usr/bin/env python

# Check that text-bound annotations in .ann file align with the
# corresponding .txt file.

import sys
import re

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

    with open(fn, 'rU') as f:
        for l in f:
            l = l.rstrip('\n')

            if not l or l.isspace():
                continue

            if l[0] != 'T':
                continue # assume not a textbound annotation
            else:
                textbounds.append(parse_textbound(l))

    # debugging
#    print >> sys.stderr, '%s: %d textbounds' % (basename(fn), len(textbounds))

    with open(txt_for_ann(fn), 'rU') as f:
        text = f.read()

    for id_, type_, start, end, ttext in textbounds:
        try:
            assert text[start:end] == ttext
        except:
            print 'Mismatch in %s: %s %d %d' % (basename(fn), id_, start, end)
            print '     reference: %s' % ttext
            print '     document : %s' % text[start:end]

def main(argv=None):
    if argv is None:
        argv = sys.argv

    if len(argv) < 2:
        print >> sys.stderr, 'Usage:', argv[0], 'FILE [FILE [...]]'
        return 1

    for fn in argv[1:]:
        process(fn)

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
