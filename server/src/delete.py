#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Deletion functionality.
'''

from __future__ import with_statement

from os.path import join as path_join
from message import Messager

def delete_document(collection, document):
    Messager.error("Document deletion not supported in this version.")
    return {}

def delete_collection(collection):
    Messager.error("Collection deletion not supported in this version.")
    return {}
     
