#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

from __future__ import with_statement

'''
Annotation statistics generation.

Author:     Pontus Stenetorp    <pontus is s u-tokyo ac jp>
Version:    2011-04-21
'''

from os.path import isfile
from os.path import join as path_join
from cPickle import load as pickle_load
from cPickle import dump as pickle_dump

from annotation import Annotations
from config import DATA_DIR
from message import display_message
from annotation import Annotations
from os.path import join
from config import DATA_DIR

### Constants
STATS_CACHE_FILE_NAME = '.stats_cache'
###

def get_stat_cache_by_dir(directory):
    return path_join(directory, STATS_CACHE_FILE_NAME)

# TODO: Quick hack, prettify and use some sort of csv format
def get_statistics(directory, base_names, use_cache=True):
    # Check if we have a cache of the costly satistics generation
    cache_file_path = get_stat_cache_by_dir(directory)
    if not isfile(cache_file_path):
        generate = True
        docstats = []
    else:
        generate = False
        with open(cache_file_path, 'rb') as cache_file:
            docstats = pickle_load(cache_file)

    if generate:
        # Generate the document statistics from scratch
        docstats = []
        for docname in base_names:
            from annotation import JOINED_ANN_FILE_SUFF
            with Annotations(
                    path_join(directory, docname),
                    read_only=True) as ann_obj:
                tb_count = len([a for a in ann_obj.get_textbounds()])
                event_count = len([a for a in ann_obj.get_events()])
                docstats.append([tb_count, event_count])

        # Cache the statistics
        try:
            with open(cache_file_path, 'wb') as cache_file:
                pickle_dump(docstats, cache_file)
        except IOError:
            display_message("Warning: could not write statistics cache file (no write permission to data directory %s?)" % directory, type='warning')
    return docstats

# TODO: Testing!
