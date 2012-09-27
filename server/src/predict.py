#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Prediction for annotation types.

Author:     Pontus Stenetorp    <pontus is s u-tokyo ac jp>
Author:     Sampo Pyysalo       <smp is s u-tokyo ac jp>
Version:    2011-11-17
'''

### Constants
CUT_OFF = 0.95
# In seconds
QUERY_TIMEOUT = 30
###

from urllib import urlencode, quote_plus
from urllib2 import urlopen, HTTPError, URLError

from annlog import log_annotation
from document import real_directory
from common import ProtocolError
from jsonwrap import loads
from projectconfig import ProjectConfiguration

# TODO: Reduce the SimSem coupling

class SimSemConnectionNotConfiguredError(ProtocolError):
    def __str__(self):
        return ('The SimSem connection has not been configured, '
                'please contact the administrator')

    def json(self, json_dic):
        json_dic['exception'] = 'simSemConnectionNotConfiguredError'


class SimSemConnectionError(ProtocolError):
    def __str__(self):
        return ('The SimSem connection returned an error or timed out, '
                'please contact the administrator')

    def json(self, json_dic):
        json_dic['exception'] = 'simSemConnectionError'


class UnknownModelError(ProtocolError):
    def __str__(self):
        return ('The client provided model not mentioned in `tools.conf`')

    def json(self, json_dic):
        json_dic['exception'] = 'unknownModelError'


def suggest_span_types(collection, document, start, end, text, model):

    pconf = ProjectConfiguration(real_directory(collection))
    for _, _, model_str, model_url in pconf.get_disambiguator_config():
        if model_str == model:
            break
    else:
        # We were unable to find a matching model
        raise SimSemConnectionNotConfiguredError

    try:
        quoted_text = quote_plus(text)
        resp = urlopen(model_url % quoted_text, None, QUERY_TIMEOUT)
    except URLError:
        # TODO: Could give more details
        raise SimSemConnectionError
    
    json = loads(resp.read())

    preds = json['result'][text.decode('utf-8')]

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
    from config import DATA_DIR
    print suggest_span_types(DATA_DIR, 'dummy', -1, -1, 'proposición', 'ner_spanish')
