#!/usr/bin/env python

# Creates key:value DBs for brat normalization support.

# Each line in the input file should have the following format:

# ID<TAB>LABEL1:STRING1<TAB>LABEL2:STRING2[...]

# Where the ID is the unique ID normalized to, and the LABEL:STRING
# pairs provide strings associated with the ID as specified by each
# string. Each line must provide at least one LABEL:STRING pair, and
# only the first LABEL:STRING pair is indexed for lookup; the rest
# provide meta-information used to differentiate entries.

# For example, for normalization to the UniProt protein DB the
# input could contain the following lines:

# P01258  Protein:Calcitonin      Organism:Human
# P01257  Protein:Calcitonin      Organism:Rat

# This script created the following databases:

# - NAME.fw.kvdb: key:ID, value:LABEL:STRING
# - NAME.bw.kvdb: key:STRING value:IDs
# - (TODO)

from __future__ import with_statement

import sys
from datetime import datetime
from os.path import dirname, basename, splitext, join

try:
    import pytc
except ImportError:
    print >> sys.stderr, """Error: failed to import pytc, the Tokyo Cabinet python bindings.

Tokyo Cabinet and pytc are required for brat key:value DBs.
Please make sure that you have installed Tokyo Cabinet

    http://fallabs.com/tokyocabinet/

and pytc

    http://pypi.python.org/pypi/pytc

before running this script.
"""
    sys.exit(1)

# Default filename extension of the database
DB_FILENAME_EXTENSION = 'kvdb'

# Default affix for "forward" (key->value) database
FW_DB_AFFIX = '.fw'

# Default affix for "backward" (value->keys) database
BW_DB_AFFIX = '.bw'

# Character separating entries in "backward" DB. This must be
# guaranteed never to occur in a key.
DB_KEY_SEPARATOR = '\t'

# Maximum number of "error" lines to output
MAX_ERROR_LINES = 100

def default_db_dir():
    # Returns the default directory into which to store the created DB.
    # This is taken from the brat configuration, config.py.

    # (Guessing we're in the brat tools/ directory...)
    sys.path.append(join(dirname(__file__), '..'))
    try:
        from config import WORK_DIR
        return WORK_DIR
    except ImportError:
        print >> sys.stderr, "Warning: failed to determine brat work directory, using current instead."
        return "."

def argparser():
    import argparse

    ap=argparse.ArgumentParser(description="Create key->value and value->key(s) DBs from given file.")
    ap.add_argument("-l", "--lowercase", default=False, action="store_true", help="Lowercase strings before DB entry.")
    ap.add_argument("-v", "--verbose", default=False, action="store_true", help="Verbose output.")
    ap.add_argument("-d", "--database", default=None, help="Base name of databases to create (default by input file name in brat work directory)")
    ap.add_argument("file", metavar="FILE", help="Normalization data (line format ID<TAB>LABEL:STRING[<TAB>LABEL:STRING...])")
    return ap

def main(argv):
    arg = argparser().parse_args(argv[1:])

    kvfn = arg.file

    if arg.database is None:
        # default database file name
        bn = splitext(basename(kvfn))[0]
        fwdbfn = join(default_db_dir(), bn+FW_DB_AFFIX+'.'+DB_FILENAME_EXTENSION)
        bwdbfn = join(default_db_dir(), bn+BW_DB_AFFIX+'.'+DB_FILENAME_EXTENSION)
    else:
        fwdbfn = arg.database+FW_DB_AFFIX
        bwdbfn = arg.database+BW_DB_AFFIX

    if arg.verbose:
        print >> sys.stderr, "Storing DBs as %s and %s" % (fwdbfn, bwdbfn)
        print >> sys.stderr, "Importing",
    start_time = datetime.now()

    import_count, duplicate_count, error_count = 0, 0, 0

    with open(kvfn, 'rU') as kvf:        
        fwdb = pytc.HDB()
        bwdb = pytc.HDB()
        fwdb.open(fwdbfn, pytc.HDBOWRITER | pytc.HDBOREADER | pytc.HDBOCREAT)
        bwdb.open(bwdbfn, pytc.HDBOWRITER | pytc.HDBOREADER | pytc.HDBOCREAT)

        for i, l in enumerate(kvf):
            l = l.rstrip('\n')

            # parse line into ID and LABEL:STRING pairs
            try:
                _id, rest = l.split('\t', 1)
            except ValueError:
                if error_count < MAX_ERROR_LINES:
                    print >> sys.stderr, "Error: skipping line %d: expected tab-separated fields, got '%s'" % (i+1, l)
                elif error_count == MAX_ERROR_LINES:
                    print >> sys.stderr, "(Too many errors; suppressing further error messages)"
                error_count += 1
                continue

            # parse LABEL:STRING pairs
            try:
                pairs = []
                for pair in rest.split('\t'):
                    label, string = pair.split(':', 1)
                    pairs.append((label, string))
            except ValueError:
                if error_count < MAX_ERROR_LINES:
                    print >> sys.stderr, "Error: skipping line %d: expected tab-separated LABEL:STRING pairs, got '%s'" % (i+1, l)
                elif error_count == MAX_ERROR_LINES:
                    print >> sys.stderr, "(Too many errors; suppressing further error messages)"
                error_count += 1
                continue

            if arg.lowercase:
                pairs = [(l,s.lower()) for l,s in pairs]

            # enter ID->rest mapping into DB
            try:
                fwdb.putkeep(_id, rest)
                import_count += 1
            except pytc.Error, e:
                if e[0] == pytc.TCEKEEP:
                    # existing key, count dup but ignore
                    duplicate_count += 1
                else:
                    # unexpected error, abort
                    raise

            # enter mapping from indexed string(s) to ID into DB

            # split into "indexed" pairs available for lookup and
            # "meta-information" pairs used only to differentiate
            # between entries
            indexed, meta = pairs[:1], pairs[1:]

            # TODO: protect against indexing the same thing
            # multiple times
            for label, value in indexed:
                bwdb.putcat(value, _id+DB_KEY_SEPARATOR)

            if arg.verbose and (i+1)%10000 == 0:
                print >> sys.stderr, '.',

    # done
    fwdb.close()
    bwdb.close()
    delta = datetime.now() - start_time

    if arg.verbose:
        print >> sys.stderr
        print >> sys.stderr, "Done in:", str(delta.seconds)+"."+str(delta.microseconds/10000), "seconds"
    
    print "Done, imported %d, skipped %d duplicate keys, skipped %d invalid lines" % (import_count, duplicate_count, error_count)

    return 0
    
if __name__ == "__main__":
    sys.exit(main(sys.argv))
