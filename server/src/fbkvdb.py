#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Functionality for access of key:value DB that supports lookup of value
by key ("forward" lookup) and keys by value ("backward" lookup).
'''

# The implementation is simple, using two key:value DBs, one
# containing the values by key (the ordinary way), and the other
# containing a set of keys (catenated with a separator) by value.
# The implementation of each key:value DB is in kvdb.py.

import sys
import kvdb

# NOTE: some of these globals need to be kept in sync with the DB
# import script (tools/norm_db_init.py).

# Normalization DB version lookup string and value (for compatibility
# checks)
NORM_DB_STRING = 'NORM_DB_VERSION'
NORM_DB_VERSION = '1.0.1'

# Normalization option lookup strings
NORM_DB_LOWERCASE = 'NORM_DB_LOWERCASE'

# Default affix for "forward" (key->value) database
FW_DB_AFFIX = '.fw'

# Default affix for "backward" (value->keys) database
BW_DB_AFFIX = '.bw'

# Character separating values in entries in DBs. This must be
# guaranteed never to occur in a key.
DB_KEY_SEPARATOR = '\t'

# Character separating labels from values in label:value pairs.
DB_LABEL_SEPARATOR = ':'

def __fw_db_name(dbname):
    '''
    Given the name of a forward-backward key:value DB, returns the
    name of the "forward" component.
    '''
    return dbname+FW_DB_AFFIX

def __bw_db_name(dbname):
    '''
    Given the name of a forward-backward key:value DB, returns the
    name of the "backward" component.
    '''
    return dbname+BW_DB_AFFIX

def get_value(dbname, key):
    '''
    Given the name of a forward-backward key:value DB and a key,
    returns the value contained in the DB for the key.
    '''
    return kvdb.get(__fw_db_name(dbname), key)

def get_version(dbname):
    '''
    Given the name of a forward-backward key:value DB, returns the
    DB version string.
    '''
    # NOTE: separator is prepended to meta-information lookups to
    # avoid clashes with normal keys.
    try:
        return get_value(dbname, DB_KEY_SEPARATOR+NORM_DB_STRING)
    except KeyError:
        return '<NO VERSION>'

def bw_is_lowercased(dbname):
    '''
    Given the name of a forward-backward key:value DB, returns
    whether the "backward" DB entries are lowercased.
    '''
    # NOTE: separator is prepended to meta-information lookups to
    # avoid clashes with normal keys.
    try:        
        lc = get_value(dbname, DB_KEY_SEPARATOR+NORM_DB_LOWERCASE)
        return lc == 'True'
    except KeyError:
        # guess not
        return False

def check_version(dbname):
    '''
    Given the name of a forward-backward key:value DB, returns True if
    the version matches that expected by this script, False otherwise.
    '''
    return get_version(dbname) == NORM_DB_VERSION

def get_pairs(dbname, key):
    '''
    Given the name of a key:value DB and a key, returns the value
    contained in the DB for the key split into LABEL:VALUE pairs.    
    '''
    return [p.split(':', 1) for p in kvdb.get(__fw_db_name(dbname), key).strip(DB_KEY_SEPARATOR).split(DB_KEY_SEPARATOR)]

def get_keys(dbname, value):
    '''
    Given the name of a forward-backward key:value DB and a value,
    returns the keys contained in the DB associated with the value.
    '''
    if bw_is_lowercased(dbname):
        value = value.lower()
    return kvdb.get(__bw_db_name(dbname), value).strip(DB_KEY_SEPARATOR).split(DB_KEY_SEPARATOR)
