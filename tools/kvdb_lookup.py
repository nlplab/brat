#!/usr/bin/env python

# Test script for lookup in a key:value DB.

# Primarily intended for testing DBs created with kvdb_init.

import sys

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

def argparser():
    import argparse

    ap=argparse.ArgumentParser(description="Print results of lookup in key:value database for keys read from STDIN.")
    ap.add_argument("-v", "--verbose", default=False, action="store_true", help="Verbose output.")
    ap.add_argument("-np", "--no-prompt", default=False, action="store_true", help="No prompt.")
    ap.add_argument("database", metavar="DATABASE", help="Name of database to read")
    return ap

def main(argv):
    arg = argparser().parse_args(argv[1:])

    dbfn = arg.database

    db = pytc.HDB()
    db.open(dbfn, pytc.HDBOREADER)

    while True:
        if not arg.no_prompt:
            print ">>> ",
        l = sys.stdin.readline()
        if not l:
            break

        l = l.rstrip()

        try:
            print db.get(l)
        except KeyError:
            if l == '':
                print "(Use Ctrl-D to exit)"
            else:
                print "(no record found for '%s')" % l
    return 0
    
if __name__ == "__main__":
    sys.exit(main(sys.argv))
