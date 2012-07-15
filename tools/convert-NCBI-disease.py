#!/usr/bin/env python

# Special-purpose script for converting the NCBI disease corpus into a
# format recognized by brat.

# The NCBI disease corpus is distributed in a line-oriented format, each
# consisting of tab-separated triples (PMID, title, text). Annotations
# are inline in pseudo-XML, e.g.

#     <category="SpecificDisease">breast cancer</category>

# Note that the texts are tokenized. This script does not attempt to
# recover the original texts but instead keep the tokenization.

from __future__ import with_statement

import sys
import os
import re
import codecs

INPUT_ENCODING = "UTF-8"
OUTPUT_ENCODING = "UTF-8"

ENTITY_TYPE = "Disease"
ATTR_TYPE = "Category"
FILE_PREFIX = "PMID-"

output_directory = None

def output(docid, text, anns):
    global output_directory

    if output_directory is None:
        txtout = sys.stdout
        soout = sys.stdout
    else:
        # add doc numbering if there is a sentence count limit,
        # implying multiple outputs per input
        outfn = os.path.join(output_directory, FILE_PREFIX+docid)
        txtout = codecs.open(outfn+'.txt', 'wt', encoding=OUTPUT_ENCODING)
        soout = codecs.open(outfn+'.ann', 'wt', encoding=OUTPUT_ENCODING)

    txtout.write(text)
    idseq = 1
    for start, end, type_, text in anns:
        # write type as separate attribute
        print >> soout, "T%d\t%s %d %d\t%s" % (idseq, ENTITY_TYPE, start, end,
                                               text)
        print >> soout, "A%d\t%s T%d %s" % (idseq, ATTR_TYPE, idseq, type_)
        idseq += 1

    if output_directory is not None:
        txtout.close()
        soout.close()

def parse(s):
    text, anns = "", []
    # tweak text: remove space around annotations and strip space
    s = re.sub(r'(<category[^<>]*>)( +)', r'\2\1', s)
    s = re.sub(r'( +)(<\/category>)', r'\2\1', s)
    rest = s.strip()
    while True:
        m = re.match(r'^(.*?)<category="([^"]+)">(.*?)</category>(.*)$', rest)
        if not m:
            break
        pre, type_, tagged, rest = m.groups()
        text += pre
        anns.append((len(text), len(text)+len(tagged), type_, tagged))
        text += tagged
    text += rest
    return text, anns

def process(fn):
    docnum = 1
    sentences = []

    with codecs.open(fn, encoding=INPUT_ENCODING) as f:
        for l in f:
            l = l.strip('\n\r')
            try:
                PMID, title, body = l.split('\t', 2)
            except ValueError:
                assert False, "Expected three TAB-separated fields, got '%s'" %l
            # In a few cases, the body text contains tabs (probably by
            # error). Replace these with space.
            body = body.replace('\t', ' ')
            t_text, t_anns = parse(title)
            b_text, b_anns = parse(body)
            # combine
            t_text += '\n'
            b_text += '\n'
            text = t_text + b_text
            anns = t_anns + [(a[0]+len(t_text),a[1]+len(t_text),a[2],a[3]) 
                             for a in b_anns]
            output(PMID, text, anns)

def main(argv):
    global output_directory

    # Take an optional "-o" arg specifying an output directory
    output_directory = None
    filenames = argv[1:]
    if len(argv) > 2 and argv[1] == "-o":
        output_directory = argv[2]
        print >> sys.stderr, "Writing output to %s" % output_directory
        filenames = argv[3:]

    fail_count = 0
    for fn in filenames:
        try:
            process(fn)
        except Exception, e:
            print >> sys.stderr, "Error processing %s: %s" % (fn, e)
            fail_count += 1

    if fail_count > 0:
        print >> sys.stderr, """
##############################################################################
#
# WARNING: error in processing %d/%d files, output is incomplete!
#
##############################################################################
""" % (fail_count, len(filenames))

if __name__ == "__main__":
    sys.exit(main(sys.argv))
