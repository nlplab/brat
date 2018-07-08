#!/usr/bin/env python

# Test script for lookup in a normalization SQL DB, intended for
# DB testing.

# TODO: duplicates parts of primary norm DB implementation, dedup.

import os.path
import sqlite3 as sqlite
import sys

TYPE_TABLES = ["names", "attributes", "infos"]
NON_EMPTY_TABLES = set(["names"])


def argparser():
    import argparse

    ap = argparse.ArgumentParser(
        description="Print results of lookup in normalization SQL DB for keys read from STDIN.")
    ap.add_argument(
        "-v",
        "--verbose",
        default=False,
        action="store_true",
        help="Verbose output.")
    ap.add_argument(
        "-np",
        "--no-prompt",
        default=False,
        action="store_true",
        help="No prompt.")
    ap.add_argument(
        "database",
        metavar="DATABASE",
        help="Name of database to read")
    return ap


def string_norm_form(s):
    return s.lower().strip().replace('-', ' ')


def datas_by_ids(cursor, ids):
    # select separately from names, attributes and infos
    responses = {}
    for table in TYPE_TABLES:
        command = '''
SELECT E.uid, L.text, N.value
FROM entities E
JOIN %s N
  ON E.id = N.entity_id
JOIN labels L
  ON L.id = N.label_id
WHERE E.uid IN (%s)''' % (table, ','.join(['?' for i in ids]))

        cursor.execute(command, list(ids))
        response = cursor.fetchall()

        # group by ID first
        for id_, label, value in response:
            if id_ not in responses:
                responses[id_] = {}
            if table not in responses[id_]:
                responses[id_][table] = []
            responses[id_][table].append([label, value])

        # short-circuit on missing or incomplete entry
        if (table in NON_EMPTY_TABLES and
                len([i for i in responses if responses[i][table] == 0]) != 0):
            return None

    # empty or incomplete?
    for id_ in responses:
        for t in NON_EMPTY_TABLES:
            if len(responses[id_][t]) == 0:
                return None

    # has expected content, format and return
    datas = {}
    for id_ in responses:
        datas[id_] = []
        for t in TYPE_TABLES:
            datas[id_].append(responses[id_].get(t, []))
    return datas


def ids_by_name(cursor, name, exactmatch=False, return_match=False):
    return ids_by_names(cursor, [name], exactmatch, return_match)


def ids_by_names(cursor, names, exactmatch=False, return_match=False):
    if not return_match:
        command = 'SELECT E.uid'
    else:
        command = 'SELECT E.uid, N.value'

    command += '''
FROM entities E
JOIN names N
  ON E.id = N.entity_id
'''
    if exactmatch:
        command += 'WHERE N.value IN (%s)' % ','.join(['?' for n in names])
    else:
        command += 'WHERE N.normvalue IN (%s)' % ','.join(['?' for n in names])
        names = [string_norm_form(n) for n in names]

    cursor.execute(command, names)
    responses = cursor.fetchall()

    if not return_match:
        return [r[0] for r in responses]
    else:
        return [(r[0], r[1]) for r in responses]


def main(argv):
    arg = argparser().parse_args(argv[1:])

    # try a couple of alternative locations based on the given DB
    # name: name as path, name as filename in work dir, and name as
    # filename without suffix in work dir
    dbn = arg.database
    dbpaths = [
        dbn, os.path.join(
            'work', dbn), os.path.join(
            'work', dbn) + '.db']

    dbfn = None
    for p in dbpaths:
        if os.path.exists(p):
            dbfn = p
            break
    if dbfn is None:
        print("Error: %s: no such file" % dbfn, file=sys.stderr)
        return 1

    try:
        connection = sqlite.connect(dbfn)
    except sqlite.OperationalError as e:
        print("Error connecting to DB %s:" % dbfn, e, file=sys.stderr)
        return 1
    cursor = connection.cursor()

    while True:
        if not arg.no_prompt:
            print(">>> ", end=' ')
        l = sys.stdin.readline()
        if not l:
            break

        l = l.rstrip()

        try:
            r = ids_by_name(cursor, l)
            if len(r) != 0:
                d = datas_by_ids(cursor, r)
                for i in d:
                    print(i + '\t', '\t'.join([' '.join(["%s:%s" % (k, v) for k, v in a]) for a in d[i]]))
            elif l == '':
                print("(Use Ctrl-D to exit)")
            else:
                print("(no record found for '%s')" % l)
        except Exception as e:
            print("Unexpected error", e, file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
