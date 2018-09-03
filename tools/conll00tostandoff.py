#!/usr/bin/env python

# Script to convert a CoNLL 2000-flavored BIO-formatted entity-tagged
# file into BioNLP ST-flavored standoff and a reconstruction of the
# original text.



import codecs
import os
import re
import sys

INPUT_ENCODING = "ASCII"
OUTPUT_ENCODING = "UTF-8"

output_directory = None


def unescape_PTB(s):
    # Returns the given string with Penn treebank escape sequences
    # replaced with the escaped text.
    return s.replace(
        "-LRB-",
        "(").replace(
        "-RRB-",
        ")").replace(
            "-LSB-",
            "[").replace(
                "-RSB-",
                "]").replace(
                    "-LCB-",
                    "{").replace(
                        "-RCB-",
                        "}").replace(
                            '``',
                            '"'). replace(
                                "''",
                                '"').replace(
                                    '\\/',
        '/')


def quote(s):
    return s in ('"', )


def space(t1, t2, quote_count=None):
    # Helper for reconstructing sentence text. Given the text of two
    # consecutive tokens, returns a heuristic estimate of whether a
    # space character should be placed between them.

    if re.match(r'^[\($]$', t1):
        return False
    if re.match(r'^[.,;%\)\?\!]$', t2):
        return False
    if quote(t1) and quote_count is not None and quote_count % 2 == 1:
        return False
    if quote(t2) and quote_count is not None and quote_count % 2 == 1:
        return False
    return True


def tagstr(start, end, ttype, idnum, text):
    # sanity checks
    assert '\n' not in text, "ERROR: newline in entity '%s'" % (text)
    assert text == text.strip(), "ERROR: tagged span contains extra whitespace: '%s'" % (text)
    return "T%d\t%s %d %d\t%s" % (idnum, ttype, start, end, text)


def output(infn, docnum, sentences):
    global output_directory

    if output_directory is None:
        txtout = sys.stdout
        soout = sys.stdout
    else:
        outfn = os.path.join(
            output_directory,
            os.path.basename(infn) +
            '-doc-' +
            str(docnum))
        txtout = codecs.open(outfn + '.txt', 'wt', encoding=OUTPUT_ENCODING)
        soout = codecs.open(outfn + '.ann', 'wt', encoding=OUTPUT_ENCODING)

    offset, idnum = 0, 1

    doctext = ""

    for si, sentence in enumerate(sentences):

        prev_token = None
        curr_start, curr_type = None, None
        quote_count = 0

        for token, ttag, ttype in sentence:

            if curr_type is not None and (ttag != "I" or ttype != curr_type):
                # a previously started tagged sequence does not
                # continue into this position.
                print(tagstr(
                    curr_start, offset, curr_type, idnum, doctext[curr_start:offset]), file=soout)
                idnum += 1
                curr_start, curr_type = None, None

            if prev_token is not None and space(
                    prev_token, token, quote_count):
                doctext = doctext + ' '
                offset += 1

            if curr_type is None and ttag != "O":
                # a new tagged sequence begins here
                curr_start, curr_type = offset, ttype

            doctext = doctext + token
            offset += len(token)

            if quote(token):
                quote_count += 1

            prev_token = token

        # leftovers?
        if curr_type is not None:
            print(tagstr(
                curr_start, offset, curr_type, idnum, doctext[curr_start:offset]), file=soout)
            idnum += 1

        if si + 1 != len(sentences):
            doctext = doctext + '\n'
            offset += 1

    print(doctext, file=txtout)


def process(fn):
    docnum = 1
    sentences = []

    with codecs.open(fn, encoding=INPUT_ENCODING) as f:

        # store (token, BIO-tag, type) triples for sentence
        current = []

        lines = f.readlines()

        for ln, l in enumerate(lines):
            l = l.strip()

            if re.match(r'^\s*$', l):
                # blank lines separate sentences
                if len(current) > 0:
                    sentences.append(current)
                current = []

                # completely arbitrary division into documents
                if len(sentences) >= 10:
                    output(fn, docnum, sentences)
                    sentences = []
                    docnum += 1

                continue

            # Assume it's a normal line. The format for spanish is
            # is word and BIO tag separated by space, and for dutch
            # word, POS and BIO tag separated by space. Try both.
            m = re.match(r'^(\S+)\s(\S+)$', l)
            if not m:
                m = re.match(r'^(\S+)\s\S+\s(\S+)$', l)
            assert m, "Error parsing line %d: %s" % (ln + 1, l)
            token, tag = m.groups()

            # parse tag
            m = re.match(r'^([BIO])((?:-[A-Za-z_]+)?)$', tag)
            assert m, "ERROR: failed to parse tag '%s' in %s" % (tag, fn)
            ttag, ttype = m.groups()
            if len(ttype) > 0 and ttype[0] == "-":
                ttype = ttype[1:]

            token = unescape_PTB(token)

            current.append((token, ttag, ttype))

        # process leftovers, if any
        if len(current) > 0:
            sentences.append(current)
        if len(sentences) > 0:
            output(fn, docnum, sentences)


def main(argv):
    global output_directory

    # Take an optional "-o" arg specifying an output directory for the results
    output_directory = None
    filenames = argv[1:]
    if len(argv) > 2 and argv[1] == "-o":
        output_directory = argv[2]
        print("Writing output to %s" % output_directory, file=sys.stderr)
        filenames = argv[3:]

    fail_count = 0
    for fn in filenames:
        try:
            process(fn)
        except Exception as e:
            print("Error processing %s: %s" % (fn, e), file=sys.stderr)
            fail_count += 1

    if fail_count > 0:
        print("""
##############################################################################
#
# WARNING: error in processing %d/%d files, output is incomplete!
#
##############################################################################
""" % (fail_count, len(filenames)), file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
