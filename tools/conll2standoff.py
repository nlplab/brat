#!/usr/bin/env python

# Script to convert a CoNLL-flavored BIO-formatted entity-tagged file
# into BioNLP ST-flavored standoff with reference to the original
# text.

import sys
import re
import os
import codecs

try:
    import psyco
    psyco.full()
except:
    pass

# what to do if an error in the tag sequence (e.g. "O I-T1" or "B-T1
# I-T2") is encountered: recover/discard the erroneously tagged 
# sequence, or abord the entire process
# TODO: add a command-line option for this
SEQUENCE_ERROR_RECOVER, SEQUENCE_ERROR_DISCARD, SEQUENCE_ERROR_FAIL = range(3)

SEQUENCE_ERROR_PROCESSING = SEQUENCE_ERROR_RECOVER

# TODO: get rid of globals

# output goes to stdout by default
out = sys.stdout
reference_directory = None
output_directory = None

def reference_text_filename(fn):
    # Tries to determine the name of the reference text file
    # for the given CoNLL output file.

    fnbase = os.path.basename(fn)
    reffn = os.path.join(reference_directory, fnbase)

    # if the file doesn't exist, try replacing the last dot-separated
    # suffix in the filename with .txt
    if not os.path.exists(reffn):
        reffn = re.sub(r'(.*)\..*', r'\1.txt', reffn)

    return reffn

def output_filename(fn):
    if output_directory is None:
        return None

    reffn = reference_text_filename(fn)
    return os.path.join(output_directory, os.path.basename(reffn).replace(".txt",".a1"))

def process(fn):
    global out

    reffn = reference_text_filename(fn)

    try:
        #reffile = open(reffn)
        reffile = codecs.open(reffn, "rt", "UTF-8")
    except:
        print >> sys.stderr, "ERROR: failed to open reference file %s" % reffn
        raise
    reftext = reffile.read()
    reffile.close()

    # ... and the tagged file
    try:
        #tagfile = open(fn)
        tagfile = codecs.open(fn, "rt", "UTF-8")
    except:
        print >> sys.stderr, "ERROR: failed to open file %s" % fn
        raise
    tagtext = tagfile.read()
    tagfile.close()

    # if an output directory is specified, write a file with an
    # appropriate name there
    if output_directory is not None:
        outfn = output_filename(fn)
        #out = codecs.open(outfn, "wt", "UTF-8")
        out = open(outfn, "wt")

    # parse CoNLL-X-flavored tab-separated BIO, storing boundaries and
    # tagged tokens. The format is one token per line, with the
    # following tab-separated fields:
    #
    #     START END TOKEN LEMMA POS CHUNK TAG
    #
    # where we're only interested in the start and end offsets
    # (START,END), the token text (TOKEN) for verification, and the
    # NER tags (TAG).  Additionally, sentence boundaries are marked by
    # blank lines in the input.

    taggedTokens = []
    for ln, l in enumerate(tagtext.split('\n')):
        if l.strip() == '':
            # skip blank lines (sentence boundary markers)
            continue

        fields = l.split('\t')
        assert len(fields) == 7, "Error: expected 7 tab-separated fields on line %d in %s, found %d: %s" % (ln+1, fn, len(fields), l.encode("UTF-8"))

        start, end, ttext = fields[0:3]
        tag = fields[6]
        start, end = int(start), int(end)

        # parse tag
        m = re.match(r'^([BIO])((?:-[A-Za-z_]+)?)$', tag)
        assert m, "ERROR: failed to parse tag '%s' in %s" % (tag, fn)
        ttag, ttype = m.groups()

        # strip off starting "-" from tagged type
        if len(ttype) > 0 and ttype[0] == "-":
            ttype = ttype[1:]

        # sanity check
        assert ((ttype == "" and ttag == "O") or
                (ttype != "" and ttag in ("B","I"))), "Error: tag format '%s' in %s" % (tag, fn)

        # verify that the text matches the original
        assert reftext[start:end] == ttext, "ERROR: text mismatch for %s on line %d: reference '%s' tagged '%s': %s" % (fn, ln+1, reftext[start:end].encode("UTF-8"), ttext.encode("UTF-8"), l.encode("UTF-8"))

        # store tagged token as (begin, end, tag, tagtype) tuple.
        taggedTokens.append((start, end, ttag, ttype))

    # transform input text from CoNLL-X flavored tabbed BIO format to
    # inline-tagged BIO format for processing (this is a bit
    # convoluted, sorry; this script written as a modification of an
    # inline-format BIO conversion script).

    ### Output for entities ###

    # returns a string containing annotation in the output format
    # for an Entity with the given properties.
    def entityStr(startOff, endOff, eType, idNum, fullText):
        # sanity checks: the string should not contain newlines and
        # should be minimal wrt surrounding whitespace
        eText = fullText[startOff:endOff]
        assert "\n" not in eText, "ERROR: newline in entity in %s: '%s'" % (fn, eText)
        assert eText == eText.strip(), "ERROR: entity contains extra whitespace in %s: '%s'" % (fn, eText)
        return "T%d\t%s %d %d\t%s" % (idNum, eType, startOff, endOff, eText)

    idIdx = 1
    prevTag, prevEnd = "O", 0
    currType, currStart = None, None
    for startoff, endoff, ttag, ttype in taggedTokens:

        # special case for surviving format errors in input: if the
        # type sequence changes without a "B" tag, change the tag
        # to allow some output (assumed to be preferable to complete
        # failure.)
        if prevTag != "O" and ttag == "I" and currType != ttype:
            if SEQUENCE_ERROR_PROCESSING == SEQUENCE_ERROR_RECOVER:
                # reinterpret as the missing "B" tag.
                ttag = "B"
            elif SEQUENCE_ERROR_PROCESSING == SEQUENCE_ERROR_DISCARD:
                ttag = "O"
            else:
                assert SEQUENCE_ERROR_PROCESSING == SEQUENCE_ERROR_FAIL
                pass # will fail on later check

        # similarly if an "I" tag occurs after an "O" tag
        if prevTag == "O" and ttag == "I":
            if SEQUENCE_ERROR_PROCESSING == SEQUENCE_ERROR_RECOVER:
                ttag = "B"            
            elif SEQUENCE_ERROR_PROCESSING == SEQUENCE_ERROR_DISCARD:
                ttag = "O"
            else:
                assert SEQUENCE_ERROR_PROCESSING == SEQUENCE_ERROR_FAIL
                pass # will fail on later check

        if prevTag != "O" and ttag != "I":
            # previous entity does not continue into this tag; output
            assert currType is not None and currStart is not None, "ERROR at %s (%d-%d) in %s" % (reftext[startoff:endoff], startoff, endoff, fn)
            
            print >> out, entityStr(currStart, prevEnd, currType, idIdx, reftext).encode("UTF-8")

            idIdx += 1

            # reset current entity
            currType, currStart = None, None

        elif prevTag != "O":
            # previous entity continues ; just check sanity
            assert ttag == "I", "ERROR in %s" % fn
            assert currType == ttype, "ERROR: entity of type '%s' continues as type '%s' in %s" % (currType, ttype, fn)
            
        if ttag == "B":
            # new entity starts
            currType, currStart = ttype, startoff
            
        prevTag, prevEnd = ttag, endoff

    # if there's an open entity after all tokens have been processed,
    # we need to output it separately
    if prevTag != "O":
        print >> out, entityStr(currStart, prevEnd, currType, idIdx, reftext).encode("UTF-8")

    if output_directory is not None:
        # we've opened a specific output for this
        out.close()

def main(argv):
    global reference_directory, output_directory


    # (clumsy arg parsing, sorry)

    # Take a mandatory "-d" arg that tells us where to find the original,
    # unsegmented and untagged reference files.

    if len(argv) < 3 or argv[1] != "-d":
        print >> sys.stderr, "USAGE:", argv[0], "-d REF-DIR [-o OUT-DIR] (FILES|DIR)"
        return 1

    reference_directory = argv[2]

    # Take an optional "-o" arg specifying an output directory for the results

    output_directory = None
    filenames = argv[3:]
    if len(argv) > 4 and argv[3] == "-o":
        output_directory = argv[4]
        print >> sys.stderr, "Writing output to %s" % output_directory
        filenames = argv[5:]


    # special case: if we only have a single file in input and it specifies
    # a directory, process all files in that directory
    input_directory = None
    if len(filenames) == 1 and os.path.isdir(filenames[0]):
        input_directory = filenames[0]
        filenames = [os.path.join(input_directory, fn) for fn in os.listdir(input_directory)]
        print >> sys.stderr, "Processing %d files in %s ..." % (len(filenames), input_directory)

    fail_count = 0
    for fn in filenames:
        try:
            process(fn)
        except Exception, e:
            print >> sys.stderr, "Error processing %s: %s" % (fn, e)
            fail_count += 1

            # if we're storing output on disk, remove the output file
            # to avoid having partially-written data
            ofn = output_filename(fn)
            try:
                os.remove(ofn)
            except:
                # never mind if that fails
                pass

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
