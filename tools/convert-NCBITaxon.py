#!/usr/bin/env python

# Special-purpose script for converting the NCBI taxonomy data dump
# into the brat normalization DB input format
# (http://brat.nlplab.org/normalization.html).

# The script expects as input the names.dmp file available from
# the NCBI FTP site (ftp://ftp.ncbi.nih.gov/pub/taxonomy/).
# As of late 2012, the following commands could be used to get
# this file (and a number of other related ones):
#
#     wget ftp://ftp.ncbi.nih.gov/pub/taxonomy/taxdump.tar.gz
#     tar xvzf taxdump.tar.gz

# The names.dmp contains four fields per line, separated by pipe
# characters ("|"): tax_id, name_txt, unique name, and name class.
# This script discards the "unique name" field (which has values such
# as "Drosophila <fruit fly, genus>"), groups the others by tax_id,
# and filters likely irrelevance names by name class.

# The file nodes.dmp contains a number of fields separated by pipe
# characters ("|"), the first being tax_id, parent tax_id, and rank.
# This script only uses the tax_id and the rank to attach taxonomixal
# rank information to normalization DB entries.

# Note that this script is not optimized in any way takes some minutes
# to run on the full NCBI taxonomy data.


import codecs
import sys

from functools import cmp_to_key


INPUT_ENCODING = "UTF-8"

# Name classes to discard from the data (unless they are the only that
# remain). These are discarded to avoid crowding the interface with a
# large number of irrelevant (e.g. "misspelling"), redundant
# (e.g. "blast name") or rarely used names (e.g. "type material").
DISCARD_NAME_CLASS = [
    "misspelling",
    "misnomer",
    "type material",
    "includes",
    "in-part",
    "authority",
    "teleomorph",
    "genbank anamorph",
    "anamorph",
    "blast name",
]

# Mapping between source data name classes and categories in output.
# Note that this excludes initial character capitalization, which is
# performed for by default as the last stage of processing.
NAME_CLASS_MAP = {
    "genbank common name": "common name",
    "genbank synonym": "synonym",
    "equivalent name": "synonym",
    "acronym": "synonym",
    "genbank acronym": "synonym",
    "genbank anamorph": "anamorph",
}

# Sort order of names for output.
NAME_ORDER_BY_CLASS = [
    "scientific name",
    "common name",
    "synonym",
] + DISCARD_NAME_CLASS


# for python3
try:
    cmp
except NameError:
    def cmp(x, y): return (x > y) - (x < y)


def main(argv):
    if len(argv) < 3:
        print("Usage:", argv[0], "names.dmp nodes.dmp", file=sys.stderr)
        return 1

    namesfn, nodesfn = argv[1:3]

    # read in nodes.dmp, store mapping from tax_id to rank
    rank_by_tax_id = {}
    with codecs.open(nodesfn, encoding=INPUT_ENCODING) as f:
        for i, l in enumerate(f):
            l = l.strip('\n\r')
            fields = l.split('|')
            fields = [t.strip() for t in fields]
            tax_id, rank = fields[0], fields[2]
            rank_by_tax_id[tax_id] = rank

    # read in names.dmp, store name_txt and name class by tax_id
    names_by_tax_id = {}
    with codecs.open(namesfn, encoding=INPUT_ENCODING) as f:
        for i, l in enumerate(f):
            l = l.strip('\n\r')

            fields = l.split('|')

            assert len(fields) >= 4, "Format error on line %d: %s" % (i + 1, l)
            fields = [t.strip() for t in fields]
            tax_id, name_txt, name_class = fields[0], fields[1], fields[3]

            if tax_id not in names_by_tax_id:
                names_by_tax_id[tax_id] = []
            names_by_tax_id[tax_id].append((name_txt, name_class))

    # filter names by class
    for tax_id in names_by_tax_id:
        for dnc in DISCARD_NAME_CLASS:
            filtered = [(t, c) for t, c in names_by_tax_id[tax_id] if c != dnc]
            if filtered:
                names_by_tax_id[tax_id] = filtered
            else:
                print("emptied", tax_id, names_by_tax_id[tax_id])

    # map classes for remaining names
    for tax_id in names_by_tax_id:
        mapped = []
        for t, c in names_by_tax_id[tax_id]:
            mapped.append((t, NAME_CLASS_MAP.get(c, c)))
        names_by_tax_id[tax_id] = mapped

    # sort for output
    nc_rank = dict((b, a) for a, b in enumerate(NAME_ORDER_BY_CLASS))
    for tax_id in names_by_tax_id:
        names_by_tax_id[tax_id].sort(key=cmp_to_key(
            lambda a, b: cmp(nc_rank[a[1]], nc_rank[b[1]])))

    # output in numerical order by taxonomy ID.
    for tax_id in sorted(names_by_tax_id, key=cmp_to_key(
            lambda a, b: cmp(int(a), int(b)))):
        sys.stdout.write(tax_id)
        for t, c in names_by_tax_id[tax_id]:
            c = c[0].upper() + c[1:]
            sys.stdout.write("\tname:%s:%s" % (c, t))
        rank = rank_by_tax_id.get(tax_id, 'unknown')
        sys.stdout.write("\tinfo:rank:%s" % rank)
        sys.stdout.write("\n")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
