#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Functionality shared between server components.

Author:     Pontus Stenetorp    <pontus is s u-tokyo ac jp>
Version:    2011-04-21
'''


class ProtocolError(Exception):
    def __init__(self):
        raise NotImplementedError, 'abstract method'

    def json(self, json_dic):
        raise NotImplementedError, 'abstract method'


# If received by ajax.cgi, no JSON will be sent
# XXX: This is an ugly hack to circumvent protocol flaws
class NoPrintJSONError(Exception):
    pass


# TODO: We have issues using this in relation to our inspection
#       in dispatch, can we make it work?
# Wrapper to send a deprecation warning to the client if debug is set
def deprecated_action(func):
    from config import DEBUG
    from functools import wraps
    from message import display_message

    @wraps(func)
    def wrapper(*args, **kwds):
        if DEBUG:
            display_message(('Client sent "%s" action '
                'which is marked as deprecated') % func.__name__,
                    type='warning')
        return func(*args, **kwds)
    return wrapper
