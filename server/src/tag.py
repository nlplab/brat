#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Tagging functionality.

Author:     Pontus Stenetorp
Version:    2011-04-22
'''

from os.path import join as path_join

from common import ProtocolError
from document import real_directory
from message import Messager
from annotation import TextAnnotations, TextBoundAnnotationWithText

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
            added_tag_ids = []
            # TODO: XXX:
            Messager.warning('Faking tagging annotation!')
            ### START: Dummy part
            from random import randint
            from annotation import TextBoundAnnotationWithText
            doc_path = path_join(real_directory(collection), document)
            with TextAnnotations(path_join(real_directory(collection),
                    document)) as ann_obj:
                # Make sure we have some text
                doc_text = ann_obj.get_document_text()
                if doc_text:
                    start = randint(0, len(doc_text) - 1)
                    end = randint(start, start + 25
                            if start + 25 <= len(doc_text) else len(doc_text))
                    _id = ann_obj.get_new_id('T')
                    ann_obj.add_annotation(TextBoundAnnotationWithText(start,
                        end, _id, 'NER', doc_text[start:end],
                        source_id=doc_path))
                    added_tag_ids.append(_id)
            ### END: Dummy part
            break
    else:
        raise UnknownTaggerError
    return {
            'added': added_tag_ids,
            }
