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
from urllib import urlencode, quote_plus
from urllib2 import urlopen, HTTPError, URLError

from annotation import TextAnnotations, TextBoundAnnotationWithText
from annotator import _json_from_ann, ModificationTracker
from common import ProtocolError
from document import real_directory
from jsonwrap import loads
from message import Messager
from projectconfig import ProjectConfiguration

### Constants
QUERY_TIMEOUT = 30
###


class UnknownTaggerError(ProtocolError):
    def __init__(self, tagger):
        self.tagger = tagger

    def __str__(self):
        return ('Tagging request received for '
                'an unknown tagger "%s"') % self.tagger

    def json(self, json_dic):
        json_dic['exception'] = 'unknownTaggerError'


class TaggerConnectionError(ProtocolError):
    def __init__(self, tagger):
        self.tagger = tagger

    def __str__(self):
        return ('Tagger service %s did not respond in %s seconds'
                ' or not at all') % (self.tagger, QUERY_TIMEOUT, )

    def json(self, json_dic):
        json_dic['exception'] = 'taggerConnectionError'


def tag(collection, document, tagger):
    pconf = ProjectConfiguration(real_directory(collection))
    for tagger_token, _, _, tagger_service_url in pconf.get_annotator_config():
        if tagger == tagger_token:
            break
    else:
        raise UnknownTaggerError(tagger)

    doc_path = path_join(real_directory(collection), document)

    with TextAnnotations(path_join(real_directory(collection),
            document)) as ann_obj:

        try:
            # Note: Can we actually fit a whole document in here?
            quoted_doc_text = quote_plus(ann_obj.get_document_text())
            resp = urlopen(tagger_service_url % quoted_doc_text, None)
#             resp = urlopen(tagger_service_url % quoted_doc_text, None,
#                 QUERY_TIMEOUT)
        except URLError:
            raise TaggerConnectionError(tagger_token)

        # TODO: Check for errors
        json_resp = loads(resp.read())

        mods = ModificationTracker()

        for ann_data in json_resp.itervalues():
            offsets = ann_data['offsets']
            # Note: We do not support discontinuous spans at this point
            assert len(offsets) == 1, 'discontinuous/null spans'
            start, end = offsets[0]
            _id = ann_obj.get_new_id('T')
            tb = TextBoundAnnotationWithText(
                    start, end,
                    _id,
                    ann_data['type'],
                    ann_data['text']
                    )
            mods.addition(tb)
            ann_obj.add_annotation(tb)

        mod_resp = mods.json_response()
        mod_resp['annotations'] = _json_from_ann(ann_obj)
        return mod_resp

if __name__ == '__main__':
    # Silly test, but helps
    tag('/BioNLP-ST_2011_ID_devel', 'PMC1874608-01-INTRODUCTION', 'random')
