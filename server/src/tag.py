#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Tagging functionality.

Author:     Pontus Stenetorp
Version:    2011-04-22
'''

from __future__ import with_statement

from os.path import join as path_join

from common import ProtocolError
from document import real_directory
from message import Messager
from annotation import TextAnnotations, TextBoundAnnotationWithText
from annotator import _json_from_ann, ModificationTracker

try:
    from config import NER_TAGGING_SERVICES
except ImportError:
    NER_TAGGING_SERVICES = tuple()

class UnknownTaggerError(ProtocolError):
    def __str__(self):
        return 'Tagging request received for an unknown tagger'
    def json(self, json_dic):
        json_dic['exception'] = 'unknownTaggerError'


def tag(collection, document, tagger):
    for tagger_token, _, _, tagger_service_url in NER_TAGGING_SERVICES:
        if tagger == tagger_token:
            mods = ModificationTracker()
            ### START: Dummy part
            # TODO: XXX: This is just for testing
            Messager.warning('Faking tagging annotation!')
            from random import randint
            from annotation import TextBoundAnnotationWithText
            doc_path = path_join(real_directory(collection), document)
            with TextAnnotations(path_join(real_directory(collection),
                    document)) as ann_obj:
                # Make sure we have some text
                doc_text = ann_obj.get_document_text()
                if doc_text:
                    start = randint(0, len(doc_text) - 1)
                    cut_off = doc_text.find('.', start)
                    if cut_off > start + 25:
                        cut_off = start + 25
                    end = randint(start, cut_off
                            if cut_off <= len(doc_text) else len(doc_text))
                    _id = ann_obj.get_new_id('T')
                    tb = TextBoundAnnotationWithText(start, end, _id, 'NER',
                            doc_text[start:end], source_id=doc_path)
                    mods.addition(tb)
                    ann_obj.add_annotation(tb)
                ### END: Dummy part
                resp = mods.json_response()
                resp['annotations'] = _json_from_ann(ann_obj)
                return resp
    else:
        raise UnknownTaggerError
    assert False, 'not a reachable state' 
