#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

"""Functionality shared between server components.

Author:     Pontus Stenetorp    <pontus is s u-tokyo ac jp>
Version:    2011-04-21
"""


class ProtocolError(Exception):
    def __init__(self):
        pass

    def __str__(self):
        # TODO: just adding __str__ to ProtocolError, not all
        # currently support it, so falling back on this assumption
        # about how to make a (nearly) human-readable string. Once
        # __str__ added to all ProtocolErrors, raise
        # NotImplementedError instead.
        return 'ProtocolError: %s (TODO: __str__() method)' % self.__class__

    def json(self, json_dic):
        raise NotImplementedError('abstract method')


class ProtocolArgumentError(ProtocolError):
    def json(self, json_dic):
        json_dic['exception'] = 'protocolArgumentError'

# If received by ajax.cgi, no JSON will be sent
# XXX: This is an ugly hack to circumvent protocol flaws


class NoPrintJSONError(Exception):
    def __init__(self, hdrs, data):
        self.hdrs = hdrs
        self.data = data


class NotImplementedError(ProtocolError):
    def json(self, json_dic):
        json_dic['exception'] = 'notImplemented'


class CollectionNotAccessibleError(ProtocolError):
    def json(self, json_dic):
        json_dic['exception'] = 'collectionNotAccessible'

    def __str__(self):
        return 'Error: collection not accessible'

# TODO: We have issues using this in relation to our inspection
#       in dispatch, can we make it work?
# Wrapper to send a deprecation warning to the client if debug is set


def deprecated_action(func):
    try:
        from config import DEBUG
    except ImportError:
        DEBUG = False
    from functools import wraps
    from message import Messager

    @wraps(func)
    def wrapper(*args, **kwds):
        if DEBUG:
            Messager.warning(
                ('Client sent "%s" action '
                 'which is marked as deprecated') %
                func.__name__,)
        return func(*args, **kwds)
    return wrapper

# relpath is not included in python 2.5; alternative implementation from
# BareNecessities package, License: MIT, Author: James Gardner
# TODO: remove need for relpath instead


def relpath(path, start):
    """Return a relative version of a path."""
    from os.path import abspath, sep, pardir, commonprefix
    from os.path import join as path_join
    if not path:
        raise ValueError("no path specified")
    start_list = abspath(start).split(sep)
    path_list = abspath(path).split(sep)
    # Work out how much of the filepath is shared by start and path.
    i = len(commonprefix([start_list, path_list]))
    rel_list = [pardir] * (len(start_list) - i) + path_list[i:]
    if not rel_list:
        return path
    return path_join(*rel_list)
