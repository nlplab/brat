#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:



"""Merge BioNLP Shared Task annotation format into a single annotation file.

find data -name '*.a1' -o -name '*.a2' -o -name '*.rel' -o -name '*.co' \
    | ./merge.py

Author:     Pontus Stenetorp
Version:    2011-01-17
"""

from collections import defaultdict
from os.path import join as join_path
from os.path import split as split_path
from sys import stdin

try:
    from argparse import ArgumentParser
except ImportError:
    from os.path import basename
    from sys import path as sys_path
    # We are most likely on an old Python and need to use our internal version
    sys_path.append(join_path(basename(__file__), '../server/lib'))
    from argparse import ArgumentParser

# Constants
# TODO: Add to options?
UNMERGED_SUFFIXES = ['a1', 'a2', 'co', 'rel']
# TODO: Add to options?
MERGED_SUFFIX = 'ann'
ARGPARSER = ArgumentParser(
    description=(
        "Merge BioNLP'11 ST annotations "
        'into a single file, reads paths from stdin'))
ARGPARSER.add_argument('-w', '--no-warn', action='store_true',
                       help='suppress warnings')
# ARGPARSER.add_argument('-d', '--debug', action='store_true',
#        help='activate additional debug output')
###


def keynat(string):
    """http://code.activestate.com/recipes/285264-natural-string-sorting/"""
    it = type(1)
    r = []
    for c in string:
        if c.isdigit():
            d = int(c)
            if r and isinstance(r[-1], it):
                r[-1] = r[-1] * 10 + d
            else:
                r.append(d)
        else:
            r.append(c.lower())
    return r


def main(args):
    argp = ARGPARSER.parse_args(args[1:])
    # ID is the stem of a file
    id_to_ann_files = defaultdict(list)
    # Index all ID;s before we merge so that we can do a little magic
    for file_path in (l.strip() for l in stdin):
        if not any((file_path.endswith(suff) for suff in UNMERGED_SUFFIXES)):
            if not argp.no_warn:
                import sys
                print((
                    'WARNING: invalid file suffix for %s, ignoring'
                ) % (file_path, ), file=sys.stderr)
            continue

        dirname, basename = split_path(file_path)
        id = join_path(dirname, basename.split('.')[0])
        id_to_ann_files[id].append(file_path)

    for id, ann_files in id_to_ann_files.items():
        # XXX: Check if output file exists
        lines = []
        for ann_file_path in ann_files:
            with open(ann_file_path, 'r') as ann_file:
                for line in ann_file:
                    lines.append(line)

        with open(id + '.' + MERGED_SUFFIX, 'w') as merged_ann_file:
            for line in lines:
                merged_ann_file.write(line)


if __name__ == '__main__':
    from sys import argv
    exit(main(argv))
