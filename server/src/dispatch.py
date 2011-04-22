#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Server request dispatching mechanism.

Author:     Pontus Stenetorp    <pontus is s u-tokyo ac jp>
Version:    2011-04-21
'''

from os.path import abspath
from os.path import join as path_join

from common import ProtocolError
from config import DATA_DIR
from document import get_directory_information, get_document
from inspect import getargspec
from itertools import izip
from jsonwrap import dumps
from message import add_messages_to_json, display_message
from svg import store_svg, retrieve_svg

### Constants
# Function call-backs
DISPATCHER = {
        'getDirectoryInformation': get_directory_information,
        'getDocument': get_document,

        'storeSVG': store_svg,
        'retrieveSVG': retrieve_svg,
        }
###


class NoActionError(ProtocolError):
    def __init__(self):
        pass

    def json(self, json_dic):
        json_dic['exception'] = 'noAction'
        # TODO: Only if debug is enabled
        display_message('Client sent no action for request', 'error')
        return json_dic


class InvalidActionError(ProtocolError):
    def __init__(self, attempted_action):
        self.attempted_action = attempted_action

    def json(self, json_dic):
        json_dic['exception'] = 'invalidAction',
        # TODO: Only if debug is enabled
        display_message('Client sent an invalid action "%s"'
                % self.attempted_action, 'error')
        return json_dic


class InvalidActionArgsError(ProtocolError):
    def __init__(self, attempted_action, missing_arg):
        self.attempted_action = attempted_action
        self.missing_arg = missing_arg

    def json(self, json_dic):
        json_dic['exception'] = 'invalidActionArgs',
        # TODO: Only if debug is enabled
        display_message(('Client did not supply argument "%s" '
            'for action "%s"')
                % (self.missing_arg, self.attempted_action), 'error')
        return json_dic


class DirectorySecurityError(ProtocolError):
    def __init__(self):
        pass

    def json(self, json_dic):
        json_dic['exception'] = 'directorySecurity',
        # TODO: Only if debug is enabled
        display_message('Client sent request for bad directory', 'error')
        return json_dic


def _directory_is_safe(dir_path):
    # TODO: Make this less naive
    if not dir_path.startswith('/'):
        # We only accept absolute paths in the data directory
        return False

    # Make a simple test that the directory is inside the data directory
    return abspath(path_join(DATA_DIR, dir_path[1:])).startswith(DATA_DIR)

def dispatch(params):
    action = params.getvalue('action')
    
    # Was an action supplied?
    if action is None:
        raise NoActionError

    # If we got a directory, check it for security
    if params.getvalue('directory') is not None:
        if not _directory_is_safe(params.getvalue('directory')):
            raise DirectorySecurityError

    # Fetch the action function for this action (if any)
    try:
        action_fuction = DISPATCHER[action]
    except KeyError:
        raise InvalidActionError(action)

    # Determine what arguments the action function expects
    args, varargs, keywords, defaults = getargspec(action_fuction)
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

    return action_fuction(*action_args)
