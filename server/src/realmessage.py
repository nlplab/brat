#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

"""Server-to-client messaging-related functionality for Brat Rapid Annotation
Tool (brat)

NOTE: This module is used by ajax.cgi prior to verifying that the Python
version is new enough to run with all our other modules. Thus this module has
to be kept as backwards compatible as possible and this over-rides any
requirements on style otherwise imposed on the project.

Author:     Pontus Stenetorp    <pontus is s u-tokyo ac jp>
Author:     Sampo Pyysalo       <smp is s u-tokyo ac jp>
Version:    2011-05-31
"""

import re

# for cleaning up control chars from a string, from
# http://stackoverflow.com/questions/92438/stripping-non-printable-characters-from-a-string-in-python
# allow tab (9) and [unix] newline (10)
__control_chars = ''.join(
    map(chr, list(range(0, 9)) + list(range(11, 32)) + list(range(127, 160))))
__control_char_re = re.compile('[%s]' % re.escape(__control_chars))


def remove_control_chars(s):
    return __control_char_re.sub('', s)


class Messager:
    __pending_messages = []

    def info(msg, duration=3, escaped=False):
        Messager.__message(msg, 'comment', duration, escaped)
    # decorator syntax only since python 2.4, staticmethod() since 2.2
    info = staticmethod(info)

    def warning(msg, duration=3, escaped=False):
        Messager.__message(msg, 'warning', duration, escaped)
    warning = staticmethod(warning)

    def error(msg, duration=3, escaped=False):
        Messager.__message(msg, 'error', duration, escaped)
    error = staticmethod(error)

    def debug(msg, duration=3, escaped=False):
        Messager.__message(msg, 'debug', duration, escaped)
    debug = staticmethod(debug)

    def output(o):
        for m, c, d in Messager.__pending_messages:
            print(c, ":", m, file=o)
    output = staticmethod(output)

    def output_json(json_dict):
        try:
            return Messager.__output_json(json_dict)
        except Exception as e:
            # TODO: do we want to always give the exception?
            json_dict['messages'] = [
                [
                    'Messager error adding messages to json (internal error in message.py, please contact administrator): %s' %
                    str(e), 'error', -1]]
            return json_dict
    output_json = staticmethod(output_json)

    def __output_json(json_dict):
        # protect against non-unicode inputs
        convertable_messages = []
        for m in Messager.__pending_messages:
            try:
                m[0].encode('utf-8')
                convertable_messages.append(m)
            except UnicodeDecodeError:
                convertable_messages.append(
                    ('[ERROR: MESSAGE THAT CANNOT BE ENCODED AS UTF-8 OMITTED]', 'error', 5))
        Messager.__pending_messages = convertable_messages

        # clean up messages by removing possible control characters
        # that may cause trouble clientside
        cleaned_messages = []
        for s, t, r in Messager.__pending_messages:
            cs = remove_control_chars(s)
            if cs != s:
                s = cs + \
                    '[NOTE: SOME NONPRINTABLE CHARACTERS REMOVED FROM MESSAGE]'
            cleaned_messages.append((s, t, r))
        Messager.__pending_messages = cleaned_messages

        # to avoid crowding the interface, combine messages with identical
        # content
        msgcount = {}
        for m in Messager.__pending_messages:
            msgcount[m] = msgcount.get(m, 0) + 1

        merged_messages = []
        for m in Messager.__pending_messages:
            if m in msgcount:
                count = msgcount[m]
                del msgcount[m]
                s, t, r = m
                if count > 1:
                    s = s + '<br/><b>[message repeated %d times]</b>' % count
                merged_messages.append((s, t, r))

        if 'messages' not in json_dict:
            json_dict['messages'] = []
        json_dict['messages'] += merged_messages
        Messager.__pending_messages = []
        return json_dict
    __output_json = staticmethod(__output_json)

    def __escape(msg):
        from cgi import escape
        return escape(msg).replace('\n', '\n<br/>\n')
    __escape = staticmethod(__escape)

    def __message(msg, type, duration, escaped):
        if not isinstance(msg, str) and not isinstance(msg, str):
            msg = str(msg)
        if not escaped:
            msg = Messager.__escape(msg)
        Messager.__pending_messages.append((msg, type, duration))
    __message = staticmethod(__message)


if __name__ == '__main__':
    # Try out Unicode, that is always fun
    Messager.warning('Hello 世界！')
    json_dic = {}
    Messager.output_json(json_dic)
    print(json_dic)
