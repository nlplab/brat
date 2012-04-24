#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Normalization support.
'''

NORM_LOOKUP_DEBUG = True

# Note: we only import DB support on invocation to avoid making the DB
# a required dependency.

# debugging
def _check_DB_version(database):
    import fbkvdb
    if not fbkvdb.check_version(database):
        from message import Messager
        Messager.warning("Warning: norm DB version mismatch: expected %s, got %s for %s" % (fbkvdb.NORM_DB_VERSION, fbkvdb.get_version(database), database))

def norm_get_name(database, key):
    import fbkvdb

    if NORM_LOOKUP_DEBUG:
        _check_DB_version(database)

    try:
        pairs = fbkvdb.get_pairs(database, key)
        # the first string is the name
        value = pairs[0][1]
    except KeyError:
        value = None

    # echo request for sync
    json_dic = {
        'database' : database,
        'key' : key,
        'value' : value
        }
    return json_dic

def norm_get_ids(database, name):
    import fbkvdb

    if NORM_LOOKUP_DEBUG:
        _check_DB_version(database)

    try:
        keys = fbkvdb.get_keys(database, name)
    except KeyError:
        keys = None

    # echo request for sync
    json_dic = {
        'database' : database,
        'value' : name,
        'keys' : keys,
        }
    return json_dic

def norm_search(database, name):
    import fbkvdb

    if NORM_LOOKUP_DEBUG:
        _check_DB_version(database)

    # get all keys by name
    try:
        keys = fbkvdb.get_keys(database, name)
    except KeyError:
        keys = []

    # get all data for each key
    data_by_key = {}
    for key in keys:
        data_by_key[key] = fbkvdb.get_pairs(database, key)

    # organize into a table format with separate header and data
    # (this matches the collection browser data format)
    unique_labels = []
    seen_label = {}
    for key in keys:
        for label, value in data_by_key[key]:
            if label not in seen_label:
                unique_labels.append(label)
            seen_label[label] = True

    # ID is first field, and datatype is "string" for all labels
    header = [(label, "string") for label in ["ID"] + unique_labels]

    # construct items
    items = []
    for key in keys:
        # make dict for lookup (note: dups will be ignored)
        data_dict = dict(data_by_key[key])
        item = [key]
        for label in unique_labels:
            if label in data_dict:
                item.append(data_dict[label])
            else:
                item.append('')
        items.append(item)

    # echo request for sync
    json_dic = {
        'database' : database,
        'query'    : name,
        'header'   : header,
        'items'    : items,
        }
    return json_dic
