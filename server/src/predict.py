#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Prediction for annotation types.

Author:     Sampo Pyysalo    <smp is s u-tokyo ac jp>
Version:    2011-11-17
'''

def suggest_span_types(collection, document, start, end):
    # array so that server can control presentation order in UI
    # independently from scores if needed
    return { 'types': [ ['Protein', 0.95],
                        ['Entity', 0.05]
                        ] }
