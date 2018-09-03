#!/usr/bin/env python

import os
import re
import sys

options = None

DEFAULT_INPUT = 'entities-anatomy.csv'

# Document ID format in BioContext data
BIOCONTEXT_ID_RE = re.compile(r'^([0-9]+|PMC[0-9]+\.[0-9]+\.[0-9])+$')


def argparser():
    import argparse

    ap = argparse.ArgumentParser(description='Convert BioContext data ' +
                                 'into brat-flavored standoff.')
    ap.add_argument('-d', '--directory', default=None,
                    help='Output directory (default output to STDOUT)')
    ap.add_argument('-e', '--entitytype', default='Anatomical_entity',
                    help='Type to assign to annotations.')
    ap.add_argument('-f', '--file', default=DEFAULT_INPUT,
                    help='BioContext data (default "' + DEFAULT_INPUT + '")')
    ap.add_argument('-n', '--no-norm', default=False, action='store_true',
                    help='Do not output normalization annotations')
    ap.add_argument('-o', '--outsuffix', default='ann',
                    help='Suffix to add to output files (default "ann")')
    ap.add_argument('-v', '--verbose', default=False, action='store_true',
                    help='Verbose output')
    ap.add_argument('id', metavar='ID/FILE', nargs='+',
                    help='IDs of documents for which to extract annotations.')
    return ap


def read_ids(fn):
    ids = set()
    with open(fn, 'rU') as f:
        for l in f:
            l = l.rstrip('\n')
            if not BIOCONTEXT_ID_RE.match(l):
                print('Warning: ID %s not in expected format' % l, file=sys.stderr)
            ids.add(l)
    return ids


def get_ids(items):
    """Given a list of either document IDs in BioContext format or names of
    files containing one ID per line, return the combined set of IDs."""

    combined = set()
    for item in items:
        if BIOCONTEXT_ID_RE.match(item):
            combined.add(item)
        else:
            # assume name of file containing IDs
            combined |= read_ids(item)
    return combined


def convert_line(l, converted):
    try:
        doc_id, id_, eid, start, end, text, group = l.split('\t')
        if id_ == 'NULL':
            return 0
        start, end = int(start), int(end)
    except BaseException:
        print('Format error: %s' % l, file=sys.stderr)
        raise

    # textbound annotation
    converted.append('T%s\t%s %d %d\t%s' % (id_, options.entitytype,
                                            start, end, text))

    # normalization (grounding) annotation
    if not options.no_norm:
        converted.append('N%s\tReference T%s %s' % (id_, id_, eid))


def output_(out, ann):
    for a in ann:
        print(a, file=out)


def output(id_, ann, append):
    if not options.directory:
        output(sys.stdout, ann)
    else:
        fn = os.path.join(options.directory, id_ + '.' + options.outsuffix)
        with open(fn, 'a' if append else 'w') as f:
            output_(f, ann)


def process_(f, ids):
    ann, current, processed = [], None, set()

    for l in f:
        l = l.strip()
        id_ = l.split('\t')[0]
        if id_ == current:
            if id_ in ids:
                convert_line(l, ann)
        else:
            # new document
            if current in ids:
                output(current, ann, current in processed)
                ann = []
                processed.add(current)
            if id_ in ids:
                if id_ in processed and options.verbose:
                    print('Warning: %s split' % id_, file=sys.stderr)
                convert_line(l, ann)
            current = id_
            # short-circuit after processing last
            if ids == processed:
                break

    if ann:
        output(current, ann, current in processed)

    for id_ in ids - processed:
        print('Warning: id %s not found' % id_, file=sys.stderr)


def process(fn, ids):
    try:
        with open(fn, 'rU') as f:
            # first line should be header; skip and confirm
            header = f.readline()
            if not header.startswith('doc_id\tid'):
                print('Warning: %s missing header' % fn, file=sys.stderr)
            process_(f, ids)
    except IOError as e:
        print(e, '(try -f argument?)', file=sys.stderr)


def main(argv=None):
    global options

    if argv is None:
        argv = sys.argv

    options = argparser().parse_args(argv[1:])

    ids = get_ids(options.id)

    process(options.file, ids)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
