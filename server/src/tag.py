#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Functionality for invoking tagging services.

Author:     Pontus Stenetorp
Version:    2011-04-22
'''

from __future__ import with_statement

from httplib import HTTPConnection
from os.path import join as path_join
from socket import error as SocketError
from urlparse import urlparse

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


class InvalidConnectionSchemeError(ProtocolError):
    def __init__(self, tagger, scheme):
        self.tagger = tagger
        self.scheme = scheme

    def __str__(self):
        return ('The tagger "%s" uses the unsupported scheme "%s"'
                ' "%s"') % (self.tagger, self.scheme, )

    def json(self, json_dic):
        json_dic['exception'] = 'unknownTaggerError'


class InvalidTaggerResponseError(ProtocolError):
    def __init__(self, tagger, response):
        self.tagger = tagger
        self.response = response

    def __str__(self):
        return (('The tagger "%s" returned an invalid JSON response, please '
            'contact the tagger service mantainer. Response: "%s"')
            % (self.tagger, self.response, ))

    def json(self, json_dic):
        json_dic['exception'] = 'unknownTaggerError'


class TaggerConnectionError(ProtocolError):
    def __init__(self, tagger, error):
        self.tagger = tagger
        self.error = error

    def __str__(self):
        return ('Tagger service %s returned the error: "%s"'
                % (self.tagger, self.error, ))

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

        url_soup = urlparse(tagger_service_url)

        if url_soup.scheme == 'http':
            Connection = HTTPConnection
        elif url_soup.scheme == 'https':
            # Delayed HTTPS import since it relies on SSL which is commonly
            #   missing if you roll your own Python, for once we should not
            #   fail early since tagging is currently an edge case and we
            #   can't allow it to bring down the whole server.
            from httplib import HTTPSConnection
            Connection = HTTPSConnection
        else:
            raise InvalidConnectionSchemeError(tagger_token, url_soup.scheme)

        conn = None
        try:
            conn = Connection(url_soup.netloc)
            req_headers = {
                    'Content-type': 'text/plain; charset=utf-8',
                    'Accept': 'application/json',
                    }
            # Build a new service URL since the request method doesn't accept
            #   a parameters argument
            service_url = url_soup.path + (
                    '?' + url_soup.query if url_soup.query else '')
            try:
                data = ann_obj.get_document_text().encode('utf-8')
                req_headers['Content-length'] = len(data)
                # Note: Trout slapping for anyone sending Unicode objects here
                conn.request('POST',
                        # As per: http://bugs.python.org/issue11898
                        # Force the url to be an ascii string
                        str(service_url),
                        data,
                        headers=req_headers)
            except SocketError, e:
                raise TaggerConnectionError(tagger_token, e)
            resp = conn.getresponse()

            # Did the request succeed?
            if resp.status != 200:
                raise TaggerConnectionError(tagger_token,
                        '%s %s' % (resp.status, resp.reason))
            # Finally, we can read the response data
            resp_data = resp.read()
        finally:
            if conn is not None:
                conn.close()

        try:
            json_resp = loads(resp_data)
        except ValueError:
            raise InvalidTaggerResponseError(tagger_token, resp_data)

        mods = ModificationTracker()

        for ann_data in json_resp.itervalues():
            assert 'offsets' in ann_data, 'Tagger response lacks offsets'
            offsets = ann_data['offsets']
            assert 'type' in ann_data, 'Tagger response lacks type'
            _type = ann_data['type']
            assert 'texts' in ann_data, 'Tagger response lacks texts'
            texts = ann_data['texts']

            # sanity
            assert len(offsets) != 0, 'Tagger response has empty offsets'
            assert len(texts) == len(offsets), 'Tagger response has different numbers of offsets and texts'

            start, end = offsets[0]
            text = texts[0]

            _id = ann_obj.get_new_id('T')

            tb = TextBoundAnnotationWithText(offsets, _id, _type, text, " " + ' '.join(texts[1:]))

            mods.addition(tb)
            ann_obj.add_annotation(tb)

        mod_resp = mods.json_response()
        mod_resp['annotations'] = _json_from_ann(ann_obj)
        return mod_resp

if __name__ == '__main__':
    # Silly test, but helps
    tag('/BioNLP-ST_2011_ID_devel', 'PMC1874608-01-INTRODUCTION', 'random')
