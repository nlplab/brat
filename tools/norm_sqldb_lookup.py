#!/usr/bin/env python

# Test script for lookup in a normalization SQL DB.

# Primarily intended for testing DBs created with norm_sqldb_init.

import sys
import os.path
import sqlite3 as sqlite

def argparser():
    import argparse

    ap=argparse.ArgumentParser(description="Print results of lookup in normalization SQL DB for keys read from STDIN.")
    ap.add_argument("-v", "--verbose", default=False, action="store_true", help="Verbose output.")
    ap.add_argument("-np", "--no-prompt", default=False, action="store_true", help="No prompt.")
    ap.add_argument("database", metavar="DATABASE", help="Name of database to read")
    return ap

def main(argv):
    arg = argparser().parse_args(argv[1:])

    dbfn = arg.database

    if not os.path.exists(dbfn):
        print >> sys.stderr, "Error: %s: no such file" % dbfn
        return 1
    
    try:
        connection = sqlite.connect(dbfn)
    except sqlite.OperationalError, e:
        print >> sys.stderr, "Error connecting to DB %s:" % dbfn, e
        return 1
    cursor = connection.cursor()

    while True:
        if not arg.no_prompt:
            print ">>> ",
        l = sys.stdin.readline()
        if not l:
            break

        l = l.rstrip()

        try:
            # search as ID
#             cursor.execute('''
# SELECT L.text, N.value
# FROM entities E
# JOIN names N
#   ON E.id = N.entity_id
# JOIN labels L
#   ON L.id = N.label_id
# WHERE E.uid=?''', (l, ))
#             print cursor.fetchall()
            # search as name
            cursor.execute('''
SELECT E.id, L.text, N.value
FROM entities E
JOIN names N
  ON E.id = N.entity_id
JOIN labels L
  ON L.id = N.label_id
WHERE N.value=?''', (l, ))
            print cursor.fetchall()
        except KeyError:
            if l == '':
                print "(Use Ctrl-D to exit)"
            else:
                print "(no record found for '%s')" % l
    return 0
    
if __name__ == "__main__":
    sys.exit(main(sys.argv))
