#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Prediction for annotation types.

Author:     Sampo Pyysalo    <smp is s u-tokyo ac jp>
Version:    2011-11-17
'''

def suggest_span_types(collection, document, start, end, text):
    # array so that server can control presentation order in UI
    # independently from scores if needed
    return { 'types': [ ['DNA_methylation', 0.9],
                        ['Protein', 0.05],
                        ['Entity', 0.05]
                        ],
             'collection': collection, # echo for reference
             'document': document,
             'start': start,
             'end': end,
             'text': text,
             }
