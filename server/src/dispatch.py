#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Server request dispatching mechanism.

Author:     Pontus Stenetorp    <pontus is s u-tokyo ac jp>
Version:    2011-04-21
'''

from os.path import abspath, normpath
from os.path import join as path_join

from annotator import create_arc, delete_arc, possible_arc_types
from annotator import create_span, delete_span
from annotator import split_span
from auth import login, logout, whoami, NotAuthorisedError
from common import ProtocolError
from config import DATA_DIR
from docimport import save_import
from document import (get_directory_information, get_document,
        get_document_timestamp)
from download import download_file, download_collection
from inspect import getargspec
from itertools import izip
from jsonwrap import dumps
from logging import info as log_info
from annlog import log_annotation
from message import Messager
from svg import store_svg, retrieve_stored
from session import get_session
from search import search_text, search_entity, search_event, search_relation
from predict import suggest_span_types

# no-op function that can be invoked by client to log a user action
def logging_no_op(collection, document, log):
    # need to return a dictionary
    return {}

### Constants
# Function call-backs
DISPATCHER = {
        'getCollectionInformation': get_directory_information,
        'getDocument': get_document,
        'getDocumentTimestamp': get_document_timestamp,
        'importDocument': save_import,

        'storeSVG': store_svg,
        'retrieveStored': retrieve_stored,
        'downloadFile': download_file,
        'downloadCollection': download_collection,

        'login': login,
        'logout': logout,
        'whoami': whoami,

        'createSpan': create_span,
        'deleteSpan': delete_span,
        'splitSpan' : split_span,

        'createArc': create_arc,
        'deleteArc': delete_arc,
        'possibleArcTypes': possible_arc_types,

        'searchText'     : search_text,
        'searchEntity'   : search_entity,
        'searchEvent'    : search_event,
        'searchRelation' : search_relation,

        'suggestSpanTypes': suggest_span_types,

        'logAnnotatorAction': logging_no_op,
        }

# Actions that correspond to annotation functionality
ANNOTATION_ACTION = set((
        'createArc',
        'deleteArc',
        'createSpan',
        'deleteSpan',
        'splitSpan',
        'suggestSpanTypes',
        ))

# Actions that will be logged as annotator actions (if so configured)
LOGGED_ANNOTATOR_ACTION = ANNOTATION_ACTION | set((
        'getDocument',
        'logAnnotatorAction',
        ))

# Actions that require authentication
REQUIRES_AUTHENTICATION = ANNOTATION_ACTION | set((
        # Document functionality
        'importDocument',
        
        # Search functionality (heavy on the CPU/disk ATM)
        'searchText',
        'searchEntity',
        'searchEvent',
        'searchRelation',
        ))

# Sanity check
for req_action in REQUIRES_AUTHENTICATION:
    assert req_action in DISPATCHER, (
            'redundant action in REQUIRES_AUTHENTICATION set')
###


class NoActionError(ProtocolError):
    def __init__(self):
        pass

    def __str__(self):
        return 'Client sent no action for request'

    def json(self, json_dic):
        json_dic['exception'] = 'noAction'
        return json_dic


class InvalidActionError(ProtocolError):
    def __init__(self, attempted_action):
        self.attempted_action = attempted_action

    def __str__(self):
        return 'Client sent an invalid action "%s"' % self.attempted_action

    def json(self, json_dic):
        json_dic['exception'] = 'invalidAction',
        return json_dic


class InvalidActionArgsError(ProtocolError):
    def __init__(self, attempted_action, missing_arg):
        self.attempted_action = attempted_action
        self.missing_arg = missing_arg

    def __str__(self):
        return 'Client did not supply argument "%s" for action "%s"' % (self.missing_arg, self.attempted_action)

    def json(self, json_dic):
        json_dic['exception'] = 'invalidActionArgs',
        return json_dic


class DirectorySecurityError(ProtocolError):
    def __init__(self, requested):
        self.requested = requested

    def __str__(self):
        return 'Client sent request for bad directory: ' + self.requested

    def json(self, json_dic):
        json_dic['exception'] = 'directorySecurity',
        return json_dic

def _directory_is_safe(dir_path):
    # TODO: Make this less naive
    if not dir_path.startswith('/'):
        # We only accept absolute paths in the data directory
        return False

    # Make a simple test that the directory is inside the data directory
    return abspath(path_join(DATA_DIR, dir_path[1:])
            ).startswith(normpath(DATA_DIR))

def dispatch(params, client_ip, client_hostname):
    action = params.getvalue('action')
    log_info(dir(params))
    log_info(str(params))

    log_info('dispatcher handling action: %s' % (action, ));
    
    # Was an action supplied?
    if action is None:
        raise NoActionError

    # If we got a directory (collection), check it for security
    if params.getvalue('collection') is not None:
        if not _directory_is_safe(params.getvalue('collection')):
            raise DirectorySecurityError(params.getvalue('collection'))

    # Make sure that we are authenticated if we are to do certain actions
    if action in REQUIRES_AUTHENTICATION:
        try:
            user = get_session()['user']
        except KeyError:
            user = None
        if user is None:
            log_info('Authorization failure for "%s" with hostname "%s"'
                     % (client_ip, client_hostname))
            raise NotAuthorisedError(action)

    # Fetch the action function for this action (if any)
    try:
        action_function = DISPATCHER[action]
    except KeyError:
        log_info('Invalid action "%s"' % action)
        raise InvalidActionError(action)

    # Determine what arguments the action function expects
    args, varargs, keywords, defaults = getargspec(action_function)
    # We will not allow this for now, there is most likely no need for it
    assert varargs is None, 'no varargs for action functions'
    assert keywords is None, 'no keywords for action functions'

    # XXX: Quick hack
    if defaults is None:
        defaults = []

    # These arguments already has default values
    default_val_by_arg = {}
    for arg, default_val in izip(args[-len(defaults):], defaults):
        default_val_by_arg[arg] = default_val

    action_args = []
    for arg_name in args:
        arg_val = params.getvalue(arg_name)

        # The client failed to provide this argument
        if arg_val is None:
            try:
                arg_val = default_val_by_arg[arg_name]
            except KeyError:
                raise InvalidActionArgsError(action, arg_name)

        action_args.append(arg_val)

    log_info('dispatcher will call %s(%s)' % (action,
        ', '.join((repr(a) for a in action_args)), ))

    # Log annotation actions separately (if so configured)
    if action in LOGGED_ANNOTATOR_ACTION:
        log_annotation(params.getvalue('collection'),
                       params.getvalue('document'),
                       'START', action, action_args)

    # TODO: log_annotation for exceptions?

    json_dic = action_function(*action_args)

    # Log annotation actions separately (if so configured)
    if action in LOGGED_ANNOTATOR_ACTION:
        log_annotation(params.getvalue('collection'),
                       params.getvalue('document'),
                       'FINISH', action, action_args)

    # Assign which action that was performed to the json_dic
    json_dic['action'] = action
    return json_dic
