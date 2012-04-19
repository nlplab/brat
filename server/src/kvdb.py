#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Functionality for key:value database access.
'''

import sys
from os.path import join as path_join

from config import WORK_DIR

try:
    import pytc
except ImportError:
    # TODO: this is not really a good way to communicate this problem.
    print >> sys.stderr, """Error: brat failed to import pytc, the Tokyo Cabinet python bindings.

Tokyo Cabinet and pytc are required for brat key:value DBs.
Please make sure that you have installed Tokyo Cabinet

    http://fallabs.com/tokyocabinet/

and pytc

    http://pypi.python.org/pypi/pytc

before using the key:value database.
"""
    raise

# the filename extension used for key:value DBs.
DB_FILENAME_EXTENSION = 'kvdb'

class dbNotFoundError(Exception):
    def __init__(self, fn):
        self.fn = fn

    def __str__(self):
        return u'Database file "%s" not found' % self.fn

def __db_filename(dbname):
    '''
    Given a key:value DB name, returns the name of the file that is
    expected to contain the DB.
    '''
    return path_join(WORK_DIR, dbname+'.'+DB_FILENAME_EXTENSION)
    
def get(dbname, key):
    '''
    Given a key value DB name and a key, returns the value contained
    in the DB for the key.
    '''

    dbfn = __db_filename(dbname)

    # open DB
    db = pytc.HDB()
    try:
        db.open(dbfn, pytc.HDBOREADER)
    except pytc.Error, e:
        if e[0] == pytc.TCENOFILE:
            raise dbNotFoundError(dbfn)
        else:
            # unexpected error
            raise

    # perform lookup
    try:
        value = db.get(key)
    except KeyError:
        # TODO: might want to have some more specific exception here
        raise 

    # done
    db.close()

    return value
