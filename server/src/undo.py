#!/usr/bin/env python

'''
Annotation undo functionality.

Author:     Pontus Stenetorp    <pontus stenetorp se>
Version:    2011-11-30
'''

from os.path import join as path_join

from annotator import delete_span
from annotation import TextAnnotations
from common import ProtocolError


class CorruptUndoTokenError(ProtocolError):
    def __str__(self):
        return 'Undo token corrupted, unable to process'

    def json(self, json_dic):
        json_dic['exception'] = 'corruptUndoTokenError'


class InvalidUndoTokenError(ProtocolError):
    def __init__(self, attrib):
        self.attrib = attrib

    def __str__(self):
        return 'Undo token missing %s' % self.attrib

    def json(self, json_dic):
        json_dic['exception'] = 'invalidUndoTokenError'


class NonUndoableActionError(ProtocolError):
    def __str__(self):
        return 'Unable to undo the given action'

    def json(self, json_dic):
        json_dic['exception'] = 'nonUndoableActionError'


def undo(collection, document, token):
    from json import loads
    try:
        token = loads(token)
    except ValueError:
        raise CorruptUndoTokenError
    try:
        _type = token['type']
    except KeyError:
        raise InvalidTokenError('type')

    if _type == 'add_tb':
        return delete_span(collection, document, token['id'])
    else:
        raise NonUndoableActionError
    assert False, 'should have returned prior to this point'

if __name__ == '__main__':
    # XXX: Path to...
    pass
