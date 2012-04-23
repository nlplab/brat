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
    return kvdb.get(__bw_db_name(dbname), value).strip(DB_KEY_SEPARATOR).split(DB_KEY_SEPARATOR)
