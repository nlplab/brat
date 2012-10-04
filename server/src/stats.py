#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

from __future__ import with_statement

'''
Annotation statistics generation.

Author:     Pontus Stenetorp    <pontus is s u-tokyo ac jp>
Version:    2011-04-21
'''

from cPickle import UnpicklingError
from cPickle import dump as pickle_dump
from cPickle import load as pickle_load
from logging import info as log_info
from os import listdir
from os.path import isfile, getmtime
from os.path import join as path_join

from annotation import Annotations, open_textfile
from config import DATA_DIR, BASE_DIR
from message import Messager
from projectconfig import get_config_path, options_get_validation

### Constants
STATS_CACHE_FILE_NAME = '.stats_cache'
###

def get_stat_cache_by_dir(directory):
    return path_join(directory, STATS_CACHE_FILE_NAME)

# TODO: Move this to a util module
def get_config_py_path():
    return path_join(BASE_DIR, 'config.py')

# TODO: Quick hack, prettify and use some sort of csv format
def get_statistics(directory, base_names, use_cache=True):
    # Check if we have a cache of the costly satistics generation
    # Also, only use it if no file is newer than the cache itself
    cache_file_path = get_stat_cache_by_dir(directory)

    try:
        cache_mtime = getmtime(cache_file_path);
    except OSError, e:
        if e.errno == 2:
            cache_mtime = -1;
        else:
            raise

    try:
        if (not isfile(cache_file_path)
                # Has config.py been changed?
                or getmtime(get_config_py_path()) > cache_mtime
                # Any file has changed in the dir since the cache was generated
                or any(True for f in listdir(directory)
                    if (getmtime(path_join(directory, f)) > cache_mtime
                    # Ignore hidden files
                    and not f.startswith('.')))
                # The configuration is newer than the cache
                or getmtime(get_config_path(directory)) > cache_mtime):
            generate = True
            docstats = []
        else:
            generate = False
            try:
                with open(cache_file_path, 'rb') as cache_file:
                    docstats = pickle_load(cache_file)
            except UnpicklingError:
                # Corrupt data, re-generate
                Messager.warning('Stats cache %s was corrupted; regenerating' % cache_file_path, -1)
                generate = True
            except EOFError:
                # Corrupt data, re-generate
                generate = True
    except OSError, e:
        Messager.warning('Failed checking file modification times for stats cache check; regenerating')
        generate = True

    # "header" and types
    stat_types = [("Entities", "int"), ("Relations", "int"), ("Events", "int")]

    if options_get_validation(directory) != 'none':
        stat_types.append(("Issues", "int"))
            
    if generate:
        # Generate the document statistics from scratch
        from annotation import JOINED_ANN_FILE_SUFF
        log_info('generating statistics for "%s"' % directory)
        docstats = []
        for docname in base_names:
            try:
                with Annotations(path_join(directory, docname), 
                        read_only=True) as ann_obj:
                    tb_count = len([a for a in ann_obj.get_entities()])
                    rel_count = (len([a for a in ann_obj.get_relations()]) +
                                 len([a for a in ann_obj.get_equivs()]))
                    event_count = len([a for a in ann_obj.get_events()])


                    if options_get_validation(directory) == 'none':
                        docstats.append([tb_count, rel_count, event_count])
                    else:
                        # verify and include verification issue count
                        try:
                            from projectconfig import ProjectConfiguration
                            projectconf = ProjectConfiguration(directory)
                            from verify_annotations import verify_annotation
                            issues = verify_annotation(ann_obj, projectconf)
                            issue_count = len(issues)
                        except:
                            # TODO: error reporting
                            issue_count = -1
                        docstats.append([tb_count, rel_count, event_count, issue_count])
            except Exception, e:
                log_info('Received "%s" when trying to generate stats' % e)
                # Pass exceptions silently, just marking stats missing
                docstats.append([-1] * len(stat_types))

        # Cache the statistics
        try:
            with open(cache_file_path, 'wb') as cache_file:
                pickle_dump(docstats, cache_file)
        except IOError, e:
            Messager.warning("Could not write statistics cache file to directory %s: %s" % (directory, e))

    return stat_types, docstats

# TODO: Testing!
