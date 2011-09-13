#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; -*- 
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Entry for FastCGI calls to brat. This is a simple wrapper around a persistent
WSGI server that delegates the processing to the FastCGI-agnostic brat server.

Depends on flup:

    http://pypi.python.org/pypi/flup/

Author:     Pontus  Stenetorp   <pontus is s u tokyo ac jp>
Version:    2010-09-14
'''

# TODO: Fail gracefully if flup is not present
from flup.server.fcgi import WSGIServer

from sys import path as sys_path
from os.path import dirname, join as path_join
from cgi import FieldStorage

sys_path.append(path_join(dirname(__file__), 'server/src'))

from dispatch import dispatch
from session import get_session

def brat_app(environ, start_response):
    # XXX: We are assuming everything went fine here... This is just a test!
    # TODO: Move most of this code into a unified agnostic server
    try:
        remote_addr = environ['REMOTE_ADDR']
    except KeyError:
        remote_addr = None
    try:
        remote_host = environ['REMOTE_HOST']
    except KeyError:
        remote_host = None

    params = FieldStorage(environ['wsgi.input'], environ=environ)

    json_dic = dispatch(params, remote_addr, remote_host)
    # XXX: If this was done properly there would be exception handling here
    from json import dumps
    start_response('200 OK', [('Content-Type', 'application/json')])
    return [dumps(json_dic, indent=4)]

if __name__ == '__main__':
    from sys import exit
    WSGIServer(brat_app).run()
    exit(0)
