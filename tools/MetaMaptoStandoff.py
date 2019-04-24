#!/usr/bin/env python

# Script to convert MetaMap "fielded" ("-N" argument) output into
# standoff with reference to the original text.

import re
import sys

# Regex for the "signature" of a metamap "fielded" output line
FIELDED_OUTPUT_RE = re.compile(r'^\d+\|')


class taggedEntity:
    def __init__(self, startOff, endOff, eType, idNum):
        self.startOff = startOff
        self.endOff = endOff
        self.eType = eType
        self.idNum = idNum

    def __str__(self):
        return "T%d\t%s %d %d" % (
            self.idNum, self.eType, self.startOff, self.endOff)


def MetaMap_lines_to_standoff(metamap_lines, reftext=None):
    tagged = []
    idseq = 1
    for l in metamap_lines:
        l = l.rstrip('\n')

        # silently skip lines that don't match the expected format
        if not FIELDED_OUTPUT_RE.match(l):
            continue

        # format is pipe-separated ("|") fields, the ones of interest
        # are in the following indices:
        # 3: preferred text form
        # 4: CUI
        # 5: semantic type (MetaMap code)
        # 8: start offset and length of match
        fields = l.split('|')

        if len(fields) < 9:
            print("Note: skipping unparseable MetaMap output line: %s" % l, file=sys.stderr)
            continue

        ctext, CUI, semtype, offset = fields[3], fields[4], fields[5], fields[8]

        # strip surrounding brackets from semantic type
        semtype = semtype.replace('[', '').replace(']', '')

        # parse length; note that this will only pick the of multiple
        # discontinuous spans if they occur (simple heuristic for the
        # head)
        m = re.match(r'^(?:\d+:\d+,)*(\d+):(\d+)$', offset)
        start, length = m.groups()
        start, length = int(start), int(length)

        tagged.append(taggedEntity(start, start + length, semtype, idseq))
        idseq += 1

    print("MetaMaptoStandoff: returning %s tagged spans" % len(
        tagged), file=sys.stderr)

    return tagged


if __name__ == "__main__":
    lines = [l for l in sys.stdin]
    standoff = MetaMap_lines_to_standoff(lines)
    for s in standoff:
        print(s)
