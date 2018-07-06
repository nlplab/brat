#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

"""Dummy Messager that can replace the real one in case it goes down. Doesn't
actually send any messages other than letting the user know of the problem. Use
e.g. as.

try:     from message import Messager except:     from sosmessage import
Messager
"""


class SosMessager:
    def output_json(json_dict):
        json_dict['messages'] = [
            ['HELP: messager down! (internal error in message.py, please contact administrator)', 'error', -1]]
        return json_dict
    output_json = staticmethod(output_json)

    def output(o):
        print('HELP: messager down! (internal error in message.py, please contact administrator)', file=o)
    output = staticmethod(output)

    def info(msg, duration=3, escaped=False): pass
    info = staticmethod(info)

    def warning(msg, duration=3, escaped=False): pass
    warning = staticmethod(warning)

    def error(msg, duration=3, escaped=False): pass
    error = staticmethod(error)

    def debug(msg, duration=3, escaped=False): pass
    debug = staticmethod(debug)
