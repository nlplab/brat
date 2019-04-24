#!/usr/bin/env python

# Converts the BioCreative 2 Gene Mention task data into brat-flavored
# standoff format.



import os
import re
import sys


def char_offsets(text, start, end, ttext):
    # Given a text and a tagged span marked by start and end offsets
    # ignoring space (plus tagged text for reference), returns the
    # character-based offsets for the marked span. This is necessary
    # as BC2 data has offsets that ignore space. Note also that input
    # offsets are assumed inclusive of last char (ala BC2), but return
    # offsets are exclusive of last (ala BioNLP ST/brat).

    # scan to start offset
    idx, nospcidx = 0, 0
    while True:
        while idx < len(text) and text[idx].isspace():
            idx += 1
        assert idx < len(text), "Error in data"
        if nospcidx == start:
            break
        nospcidx += 1
        idx += 1

    char_start = idx

    # scan to end offset
    while nospcidx < end:
        nospcidx += 1
        idx += 1
        while idx < len(text) and text[idx].isspace():
            idx += 1

    char_end = idx + 1

    # special case allowing for slight adjustment for known error in
    # BC2 data
    if (text[char_start:char_end] == '/translation upstream factor' and
            ttext == 'translation upstream factor'):
        print("NOTE: applying special-case fix ...", file=sys.stderr)
        char_start += 1

    # sanity
    ref_text = text[char_start:char_end]
    assert ref_text == ttext, "Mismatch: '%s' vs '%s' [%d:%d] (%s %d-%d)" % (
        ttext, ref_text, char_start, char_end, text, start, end)

    return char_start, char_end


def main(argv):
    if len(argv) != 4:
        print("Usage:", argv[0], "BC2TEXT BC2TAGS OUTPUT-DIR", file=sys.stderr)
        return 1

    textfn, tagfn, outdir = argv[1:]

    # read in tags, store by sentence ID
    tags = {}
    with open(tagfn, 'rU') as tagf:
        for l in tagf:
            l = l.rstrip('\n')
            m = re.match(r'^([^\|]+)\|(\d+) (\d+)\|(.*)$', l)
            assert m, "Format error in %s: %s" % (tagfn, l)
            sid, start, end, text = m.groups()
            start, end = int(start), int(end)

            if sid not in tags:
                tags[sid] = []
            tags[sid].append((start, end, text))

    # read in sentences, store by sentence ID
    texts = {}
    with open(textfn, 'rU') as textf:
        for l in textf:
            l = l.rstrip('\n')
            m = re.match(r'(\S+) (.*)$', l)
            assert m, "Format error in %s: %s" % (textfn, l)
            sid, text = m.groups()

            assert sid not in texts, "Error: duplicate ID %s" % sid
            texts[sid] = text

    # combine tags with sentences, converting offsets into
    # character-based ones. (BC2 data offsets ignore space)
    offsets = {}
    for sid in texts:
        offsets[sid] = []
        for start, end, ttext in tags.get(sid, []):
            soff, eoff = char_offsets(texts[sid], start, end, ttext)
            offsets[sid].append((soff, eoff))

    # output one .txt and one .a1 file per sentence
    for sid in texts:
        with open(os.path.join(outdir, sid + ".txt"), 'w') as txtf:
            print(texts[sid], file=txtf)
        with open(os.path.join(outdir, sid + ".ann"), 'w') as annf:
            tidx = 1
            for soff, eoff in offsets[sid]:
                print("T%d\tGENE %d %d\t%s" % (
                    tidx, soff, eoff, texts[sid][soff:eoff]), file=annf)
                tidx += 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
