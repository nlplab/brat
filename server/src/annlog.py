#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Annotation operation logging mechanism.

Author:     Pontus Stenetorp    <pontus is s u-tokyo ac jp>
Author:     Sampo Pyysalo       <smp is s u-tokyo ac jp>
Version:    2011-11-22
'''

try:
    from config import ANNOTATION_LOG
except ImportError:
    # annotation logging switched off not defined
    ANNOTATION_LOG = None

import logging
from session import get_session
from message import Messager
from inspect import getargspec

def annotation_logging_active():
    """
    Returns true if annotation logging is being performed, false
    otherwise.
    """
    return ann_logger() is not None

def ann_logger():
    """
    Lazy initializer for the annotation logger. Returns None if
    annotation logging is not configured and a logger otherwise.
    """
    if ann_logger.__logger == False:
        # not initialized
        if ANNOTATION_LOG is None:
            # not configured
            ann_logger.__logger = None
        else:
            # initialize
            try:
                l = logging.getLogger('annotation')
                l.setLevel(logging.INFO)
                handler = logging.FileHandler(ANNOTATION_LOG)
                handler.setLevel(logging.INFO)
                formatter = logging.Formatter('%(asctime)s\t%(message)s')
                handler.setFormatter(formatter)
                l.addHandler(handler)
                ann_logger.__logger = l
            except IOError, e:
                Messager.error("""Error: failed to initialize annotation log %s: %s.
Edit action not logged.
Please check ANNOTATION_LOG setting in config.py""" % (ANNOTATION_LOG, e))
                logging.error("Failed to initialize annotation log %s: %s" % 
                              (ANNOTATION_LOG, e))
                ann_logger.__logger = None                
                
    return ann_logger.__logger
ann_logger.__logger = False

# local abbrev; can't have literal tabs in log fields
def _detab(s):
    return str(s).replace('\t', '\\t')

def log_annotation(collection, document, status, action, args):
    """
    Logs an annotation operation of type action in the given document
    of the given collection. Status is an arbitrary string marking the
    status of processing the request and args a dictionary giving
    the arguments of the action.
    """

    l = ann_logger()

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
