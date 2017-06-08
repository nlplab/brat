#!/usr/bin/env python

# Creates SQL and simstring DBs for brat normalization support.

# Each line in the input file should have the following format:

# ID<TAB>TYPE1:LABEL1:STRING1<TAB>TYPE2:LABEL2:STRING2[...]

# Where the ID is the unique ID normalized to, and the
# TYPE:LABEL:STRING triplets provide various information associated
# with the ID.

# Each TYPE must be one of the following:

# - "name": STRING is name or alias
# - "attr": STRING is non-name attribute
# - "info": STRING is non-searchable additional information

# Each LABEL provides a human-readable label for the STRING. LABEL
# values are not used for querying.

# For example, for normalization to the UniProt protein DB the input
# could contain lines such as the following:

# P01258  name:Protein:Calcitonin      attr:Organism:Human
# P01257  name:Protein:Calcitonin      attr:Organism:Rat

# In search, each query string must match at least part of some "name"
# field to retrieve an ID. Parts of query strings not matching a name
# are used to query "attr" fields, allowing these to be used to
# differentiate between ambiguous names. Thus, for the above example,
# a search for "Human Calcitonin" would match P01258 but not P01257.
# Fields with TYPE "info" are not used for querying.

from __future__ import with_statement

import sys
import codecs
from datetime import datetime
from os.path import dirname, basename, splitext, join

import sqlite3 as sqlite

try:
    import simstring
except ImportError:
    from message import Messager    
    errorstr = """
    Error: failed to import the simstring library.
    This library is required for approximate string matching DB lookup.
    Please install simstring and its python bindings from 
    http://www.chokkan.org/software/simstring/
"""
    print >> sys.stderr, errorstr
    sys.exit(1)

# Default encoding for input text
DEFAULT_INPUT_ENCODING = 'UTF-8'

# Normalization DB version lookup string and value (for compatibility
# checks)
NORM_DB_STRING = 'NORM_DB_VERSION'
NORM_DB_VERSION = '1.0.1'

# Default filename extension of the SQL database
SQL_DB_FILENAME_EXTENSION = 'db'

# Filename extension used for simstring database file.
SS_DB_FILENAME_EXTENSION = 'ss.db'

# Length of n-grams in simstring DBs
DEFAULT_NGRAM_LENGTH = 3

# Whether to include marks for begins and ends of strings
DEFAULT_INCLUDE_MARKS = False

# Maximum number of "error" lines to output
MAX_ERROR_LINES = 100

# Supported TYPE values
TYPE_VALUES = ["name", "attr", "info"]

# Which SQL DB table to enter type into
TABLE_FOR_TYPE = {
    "name" : "names",
    "attr" : "attributes",
    "info" : "infos",
}

# Whether SQL table includes a normalized string form
TABLE_HAS_NORMVALUE = {
    "names" : True,
    "attributes" : True,
    "infos" : False,
}

# sanity
assert set(TYPE_VALUES) == set(TABLE_FOR_TYPE.keys())
assert set(TABLE_FOR_TYPE.values()) == set(TABLE_HAS_NORMVALUE.keys())

# SQL for creating tables and indices
CREATE_TABLE_COMMANDS = [
"""
CREATE TABLE entities (
  id INTEGER PRIMARY KEY,
  uid VARCHAR(255) UNIQUE
);
""",
"""
CREATE TABLE labels (
  id INTEGER PRIMARY KEY,
  text VARCHAR(255)
);
""",
"""
CREATE TABLE names (
  id INTEGER PRIMARY KEY,
  entity_id INTEGER REFERENCES entities (id),
  label_id INTEGER REFERENCES labels (id),
  value VARCHAR(255),
  normvalue VARCHAR(255)
);
""",
"""
CREATE TABLE attributes (
  id INTEGER PRIMARY KEY,
  entity_id INTEGER REFERENCES entities (id),
  label_id INTEGER REFERENCES labels (id),
  value VARCHAR(255),
  normvalue VARCHAR(255)
);
""",
"""
CREATE TABLE infos (
  id INTEGER PRIMARY KEY,
  entity_id INTEGER REFERENCES entities (id),
  label_id INTEGER REFERENCES labels (id),
  value VARCHAR(255)
);
""",
]
CREATE_INDEX_COMMANDS = [
"CREATE INDEX entities_uid ON entities (uid);",
"CREATE INDEX names_value ON names (value);",
"CREATE INDEX names_normvalue ON names (normvalue);",
"CREATE INDEX names_entity_id ON names (entity_id);",
"CREATE INDEX attributes_value ON attributes (value);",
"CREATE INDEX attributes_normvalue ON attributes (normvalue);",
"CREATE INDEX attributes_entity_id ON attributes (entity_id);",
#"CREATE INDEX infos_value ON infos (value);", # unnecessary, not searchable
"CREATE INDEX infos_entity_id ON infos (entity_id);",
]

# SQL for selecting strings to be inserted into the simstring DB for
# approximate search
SELECT_SIMSTRING_STRINGS_COMMAND = """
SELECT DISTINCT(normvalue) FROM names
UNION 
SELECT DISTINCT(normvalue) from attributes;
"""

# Normalizes a given string for search. Used to implement
# case-insensitivity and similar in search.
# NOTE: this is a different sense of "normalization" than that
# implemented by a normalization DB as a whole: this just applies to
# single strings.
# NOTE2: it is critically important that this function is performed
# identically during DB initialization and actual lookup.
# TODO: enforce a single implementation.
def string_norm_form(s):
    return s.lower().strip().replace('-', ' ')

def default_db_dir():
    # Returns the default directory into which to store the created DBs.
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

    ap=argparse.ArgumentParser(description="Create normalization DBs for given file")
    ap.add_argument("-v", "--verbose", default=False, action="store_true", help="Verbose output")
    ap.add_argument("-d", "--database", default=None, help="Base name of databases to create (default by input file name in brat work directory)")
    ap.add_argument("-e", "--encoding", default=DEFAULT_INPUT_ENCODING, help="Input text encoding (default "+DEFAULT_INPUT_ENCODING+")")
    ap.add_argument("file", metavar="FILE", help="Normalization data")
    return ap

def sqldb_filename(dbname):
    '''
    Given a DB name, returns the name of the file that is expected to
    contain the SQL DB.
    '''
    return join(default_db_dir(), dbname+'.'+SQL_DB_FILENAME_EXTENSION)

def ssdb_filename(dbname):
    '''
    Given a DB name, returns the  name of the file that is expected to
    contain the simstring DB.
    '''
    return join(default_db_dir(), dbname+'.'+SS_DB_FILENAME_EXTENSION)

def main(argv):
    arg = argparser().parse_args(argv[1:])

    # only simstring library default supported at the moment (TODO)
    assert DEFAULT_NGRAM_LENGTH == 3, "Error: unsupported n-gram length"
    assert DEFAULT_INCLUDE_MARKS == False, "Error: begin/end marks not supported"

    infn = arg.file

    if arg.database is None:
        # default database file name
        bn = splitext(basename(infn))[0]
        sqldbfn = sqldb_filename(bn)
        ssdbfn = ssdb_filename(bn)
    else:
        sqldbfn = arg.database+'.'+SQL_DB_FILENAME_EXTENSION
        ssdbfn = arg.database+'.'+SS_DB_FILENAME_EXTENSION

    if arg.verbose:
        print >> sys.stderr, "Storing SQL DB as %s and" % sqldbfn
        print >> sys.stderr, "  simstring DB as %s" % ssdbfn
    start_time = datetime.now()

    import_count, duplicate_count, error_count, simstring_count = 0, 0, 0, 0

    with codecs.open(infn, 'rU', encoding=arg.encoding) as inf:        

        # create SQL DB
        try:
            connection = sqlite.connect(sqldbfn)
        except sqlite.OperationalError, e:
            print >> sys.stderr, "Error connecting to DB %s:" % sqldbfn, e
            return 1
        cursor = connection.cursor()

        # create SQL tables
        if arg.verbose:
            print >> sys.stderr, "Creating tables ...",

        for command in CREATE_TABLE_COMMANDS:
            try:
                cursor.execute(command)
            except sqlite.OperationalError, e:
                print >> sys.stderr, "Error creating %s:" % sqldbfn, e, "(DB exists?)"
                return 1

        # import data
        if arg.verbose:
            print >> sys.stderr, "done."
            print >> sys.stderr, "Importing data ...",

        next_eid = 1
        label_id = {}
        next_lid = 1
        next_pid = dict([(t,1) for t in TYPE_VALUES])

        for i, l in enumerate(inf):
            l = l.rstrip('\n')

            # parse line into ID and TYPE:LABEL:STRING triples
            try:
                id_, rest = l.split('\t', 1)
            except ValueError:
                if error_count < MAX_ERROR_LINES:
                    print >> sys.stderr, "Error: skipping line %d: expected tab-separated fields, got '%s'" % (i+1, l)
                elif error_count == MAX_ERROR_LINES:
                    print >> sys.stderr, "(Too many errors; suppressing further error messages)"
                error_count += 1
                continue

            # parse TYPE:LABEL:STRING triples
            try:
                triples = []
                for triple in rest.split('\t'):
                    type_, label, string = triple.split(':', 2)
                    if type_ not in TYPE_VALUES:
                        print >> sys.stderr, "Unknown TYPE %s" % type_
                    triples.append((type_, label, string))
            except ValueError:
                if error_count < MAX_ERROR_LINES:
                    print >> sys.stderr, "Error: skipping line %d: expected tab-separated TYPE:LABEL:STRING triples, got '%s'" % (i+1, rest)
                elif error_count == MAX_ERROR_LINES:
                    print >> sys.stderr, "(Too many errors; suppressing further error messages)"
                error_count += 1
                continue

            # insert entity
            eid = next_eid
            next_eid += 1
            try:
                cursor.execute("INSERT into entities VALUES (?, ?)", (eid, id_))
            except sqlite.IntegrityError, e:
                if error_count < MAX_ERROR_LINES:
                    print >> sys.stderr, "Error inserting %s (skipping): %s" % (id_, e)
                elif error_count == MAX_ERROR_LINES:
                    print >> sys.stderr, "(Too many errors; suppressing further error messages)"
                error_count += 1
                continue

            # insert new labels (if any)
            labels = set([l for t,l,s in triples])
            new_labels = [l for l in labels if l not in label_id]
            for label in new_labels:
                lid = next_lid
                next_lid += 1
                cursor.execute("INSERT into labels VALUES (?, ?)", (lid, label))
                label_id[label] = lid

            # insert associated strings
            for type_, label, string in triples:
                table = TABLE_FOR_TYPE[type_]
                pid = next_pid[type_]
                next_pid[type_] += 1
                lid = label_id[label] # TODO
                if TABLE_HAS_NORMVALUE[table]:
                    normstring = string_norm_form(string)
                    cursor.execute("INSERT into %s VALUES (?, ?, ?, ?, ?)" % table,
                                   (pid, eid, lid, string, normstring))
                else:
                    cursor.execute("INSERT into %s VALUES (?, ?, ?, ?)" % table,
                                   (pid, eid, lid, string))

            import_count += 1

            if arg.verbose and (i+1)%10000 == 0:
                print >> sys.stderr, '.',

        if arg.verbose:
            print >> sys.stderr, "done."

        # create SQL indices
        if arg.verbose:
            print >> sys.stderr, "Creating indices ...",

        for command in CREATE_INDEX_COMMANDS:
            try:
                cursor.execute(command)
            except sqlite.OperationalError, e:
                print >> sys.stderr, "Error creating index", e
                return 1

        if arg.verbose:
            print >> sys.stderr, "done."

        # wrap up SQL table creation
        connection.commit()

        # create simstring DB
        if arg.verbose:
            print >> sys.stderr, "Creating simstring DB ...",
        
        try:
            ssdb = simstring.writer(ssdbfn)
            for row in cursor.execute(SELECT_SIMSTRING_STRINGS_COMMAND):
                # encode as UTF-8 for simstring
                s = row[0].encode('utf-8')
                ssdb.insert(s)
                simstring_count += 1
            ssdb.close()
        except:
            print >> sys.stderr, "Error building simstring DB"
            raise

        if arg.verbose:
            print >> sys.stderr, "done."

        cursor.close()

    # done
    delta = datetime.now() - start_time

    if arg.verbose:
        print >> sys.stderr
        print >> sys.stderr, "Done in:", str(delta.seconds)+"."+str(delta.microseconds/10000), "seconds"
    
    print "Done, imported %d entries (%d strings), skipped %d duplicate keys, skipped %d invalid lines" % (import_count, simstring_count, duplicate_count, error_count)

    return 0
    
if __name__ == "__main__":
    sys.exit(main(sys.argv))
