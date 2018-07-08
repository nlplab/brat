#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

"""Annotation operation logging mechanism.

Author:     Pontus Stenetorp    <pontus is s u-tokyo ac jp>
Author:     Sampo Pyysalo       <smp is s u-tokyo ac jp>
Version:    2011-11-22
"""

import logging
from os.path import join as path_join
from os.path import isabs

from config import DATA_DIR

from message import Messager
from projectconfig import options_get_annlogfile
from session import get_session


def real_directory(directory, rel_to=DATA_DIR):
    assert isabs(directory), 'directory "%s" is not absolute' % directory
    return path_join(rel_to, directory[1:])


def annotation_logging_active(directory):
    """Returns true if annotation logging is being performed for the given
    directory, false otherwise."""
    return ann_logger(directory) is not None


def ann_logger(directory):
    """Lazy initializer for the annotation logger.

    Returns None if annotation logging is not configured for the given
    directory and a logger otherwise.
    """
    if not ann_logger.__logger:
        # not initialized
        annlogfile = options_get_annlogfile(directory)
        if annlogfile == '<NONE>':
            # not configured
            ann_logger.__logger = None
        else:
            # initialize
            try:
                l = logging.getLogger('annotation')
                l.setLevel(logging.INFO)
                handler = logging.FileHandler(annlogfile)
                handler.setLevel(logging.INFO)
                formatter = logging.Formatter('%(asctime)s\t%(message)s')
                handler.setFormatter(formatter)
                l.addHandler(handler)
                ann_logger.__logger = l
            except IOError as e:
                Messager.error("""Error: failed to initialize annotation log %s: %s.
Edit action not logged.
Please check the Annotation-log logfile setting in tools.conf""" % (annlogfile, e))
                logging.error("Failed to initialize annotation log %s: %s" %
                              (annlogfile, e))
                ann_logger.__logger = None

    return ann_logger.__logger


ann_logger.__logger = False

# local abbrev; can't have literal tabs in log fields


def _detab(s):
    return str(s).replace('\t', '\\t')


def log_annotation(collection, document, status, action, args):
    """Logs an annotation operation of type action in the given document of the
    given collection.

    Status is an arbitrary string marking the status of processing the
    request and args a dictionary giving the arguments of the action.
    """

    real_dir = real_directory(collection)

    l = ann_logger(real_dir)

    if not l:
        return False

    try:
        user = get_session()['user']
    except KeyError:
        user = 'anonymous'

    # avoid redundant logging (assuming first two args are
    # collection and document)
    # TODO: get rid of the assumption, parse the actual args
    other_args = args[2:]

    # special case for "log only" action: don't redundantly
    # record the uninformative action name, but treat the
    # first argument as the 'action'.
    if action == 'logAnnotatorAction':
        action = other_args[0]
        other_args = other_args[1:]

    l.info('%s\t%s\t%s\t%s\t%s\t%s' % (_detab(user), _detab(collection),
                                       _detab(document), _detab(status),
                                       _detab(action),
                                       '\t'.join([_detab(str(a)) for a in other_args])))
