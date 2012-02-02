#!/usr/bin/env python

# Script to convert a CoNLL X (2006) tabbed dependency tree format
# file into BioNLP ST-flavored standoff and a reconstruction of the
# original text.

from __future__ import with_statement

import sys
import re
import os
import codecs

# whether to output an explicit root note
OUTPUT_ROOT = True
# the string to use to represent the root node
ROOT_STR = 'ROOT'

INPUT_ENCODING = "UTF-8"
OUTPUT_ENCODING = "UTF-8"

output_directory = None

def tokstr(start, end, ttype, idnum, text):
    # sanity checks
    assert '\n' not in text, "ERROR: newline in entity '%s'" % (text)
    assert text == text.strip(), "ERROR: tagged span contains extra whitespace: '%s'" % (text)
    return "T%d\t%s %d %d\t%s" % (idnum, ttype, start, end, text)

def depstr(depid, headid, rel, idnum):
    return "R%d\t%s Arg1:T%d Arg2:T%d" % (idnum, rel, headid, depid)

def output(infn, docnum, sentences):
    global output_directory

    if output_directory is None:
        txtout = sys.stdout
        soout = sys.stdout
    else:
        outfn = os.path.join(output_directory, os.path.basename(infn)+'-doc-'+str(docnum))
        txtout = codecs.open(outfn+'.txt', 'wt', encoding=OUTPUT_ENCODING)
        soout = codecs.open(outfn+'.ann', 'wt', encoding=OUTPUT_ENCODING)

    offset, idnum, ridnum = 0, 1, 1

    doctext = ""

    for si, sentence in enumerate(sentences):
        tokens, deps = sentence

        # store mapping from per-sentence token sequence IDs to
        # document-unique token IDs
        idmap = {}

        # output tokens
        prev_form = None

        if OUTPUT_ROOT:
            # add an explicit root node with seq ID 0 (zero)
            tokens = [('0', ROOT_STR, ROOT_STR)] + tokens

        for ID, form, POS in tokens:

            if prev_form is not None:
                doctext = doctext + ' '
                offset += 1

            # output a token annotation
            print >> soout, tokstr(offset, offset+len(form), POS, idnum, form)
#             print >> soout, tokstr(offset, offset+len(form), "T", idnum, form)
            assert ID not in idmap, "Error in data: dup ID"
            idmap[ID] = idnum
            idnum += 1

            doctext = doctext + form
            offset += len(form)
            
            prev_form = form

        # output dependencies
        for dep, head, rel in deps:

            # if root is not added, skip deps to the root (idx 0)
            if not OUTPUT_ROOT and head == '0':
                continue

            print >> soout, depstr(idmap[dep], idmap[head], rel, ridnum)
            ridnum += 1
        
        if si+1 != len(sentences):
            doctext = doctext + '\n'        
            offset += 1
            
    print >> txtout, doctext

def process(fn):
    docnum = 1
    sentences = []

    with codecs.open(fn, encoding=INPUT_ENCODING) as f:

        tokens, deps = [], []

        lines = f.readlines()

        for ln, l in enumerate(lines):
            l = l.strip()

            # igore lines starting with "#" as comments
            if len(l) > 0 and l[0] == "#":
                continue

            if re.match(r'^\s*$', l):
                # blank lines separate sentences
                if len(tokens) > 0:
                    sentences.append((tokens, deps))
                tokens, deps = [], []

                # completely arbitrary division into documents
                if len(sentences) >= 10:
                    output(fn, docnum, sentences)
                    sentences = []
                    docnum += 1

                continue

            # Assume it's a normal line. The format is tab-separated,
            # with ten fields, of which the following are used here
            # (from http://ilk.uvt.nl/conll/):
            # 1 ID     Token counter, starting at 1 for each new sentence.
            # 2 FORM   Word form or punctuation symbol.
            # 5 POSTAG Fine-grained part-of-speech tag
            # 7 HEAD   Head of the current token
            # 8 DEPREL Dependency relation to the HEAD.
            fields = l.split('\t')

            assert len(fields) == 10, "Format error on line %d in %s: %s" % (ln, fn, l)

            ID, form, POS = fields[0], fields[1], fields[4]
            head, rel = fields[6], fields[7]

            tokens.append((ID, form, POS))
            deps.append((ID, head, rel))

        # process leftovers, if any
        if len(tokens) > 0:
            sentences.append((tokens, deps))
        if len(sentences) > 0:
            output(fn, docnum, sentences)

def main(argv):
    global output_directory

    # Take an optional "-o" arg specifying an output directory for the results
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

    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
