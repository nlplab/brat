#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Prediction for annotation types.

Author:     Sampo Pyysalo       <smp is s u-tokyo ac jp>
Author:     Pontus Stenetorp    <pontus is s u-tokyo ac jp>
Version:    2011-11-17
'''

### Constants
SIMSEM_HOST = None
SIMSEM_PORT = None
SIMSEM_URL = 'http://%s:%s/' % (SIMSEM_HOST, SIMSEM_PORT)
CUT_OFF = 0.95
###

from urllib import urlencode
from urllib2 import urlopen, HTTPError, URLError

from annlog import log_annotation
from common import ProtocolError
from jsonwrap import loads


class SimSemConnectionNotConfiguredError(ProtocolError):
    def __str__(self):
        return ('The SimSem connection has not been configured, '
                'please contact the administrator')

    def json(self, json_dic):
        json_dic['exception'] = 'simSemConnectionNotConfiguredError'


class SimSemConnectionError(ProtocolError):
    def __str__(self):
        return ('The SimSem connection returned an error, '
                'please contact the administrator')

    def json(self, json_dic):
        json_dic['exception'] = 'simSemConnectionError'


def suggest_span_types(collection, document, start, end, text):
    if SIMSEM_HOST is None or SIMSEM_PORT is None:
        raise SimSemConnectionNotConfiguredError

    req_data = urlencode({
            'classify': text,
            })

    try:
        resp = urlopen('%s?%s' % (SIMSEM_URL, req_data,))
    except URLError:
        # TODO: Could give more details
        raise SimSemConnectionError

    json = loads(resp.read())

    preds = json['result'][text]

    selected_preds = []
    conf_sum = 0
    for cat, conf in preds:
        selected_preds.append((cat, conf, ))
        conf_sum += conf
        if conf_sum >= CUT_OFF:
            break

    log_annotation(collection, document, 'DONE', 'suggestion',
            [None, None, text, ] + [selected_preds, ])

    # array so that server can control presentation order in UI
    # independently from scores if needed
    return { 'types': selected_preds,
             'collection': collection, # echo for reference
             'document': document,
             'start': start,
             'end': end,
             'text': text,
             }

if __name__ == '__main__':
    print suggest_span_types('dummy', 'dummy', -1, -1, 'paracetamol')
