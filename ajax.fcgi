#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; -*- 
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Entry for FastCGI calls to brat. This is a simple wrapper around a persistent
WSGI server that delegates the processing to the FastCGI-agnostic server.

Depends on flup:

    http://pypi.python.org/pypi/flup/

Author:     Pontus  Stenetorp   <pontus is s u tokyo ac jp>
Version:    2010-09-14
'''

# Standard library imports
from sys import path as sys_path
from os.path import dirname, join as path_join
from cgi import FieldStorage

# Library imports
# TODO: Fail gracefully if flup is not present
try:
    from flup.server.fcgi import WSGIServer
except ImportError:
    # We do have carry it ourselves, just-in-case
    sys_path.append(path_join(dirname(__file__), 'server/lib/', 'flup-1.0.2'))
    from flup.server.fcgi import WSGIServer

# Local imports
sys_path.append(path_join(dirname(__file__), 'server/src'))

from server import serve

def stav_app(environ, start_response):
    # Get the data required by the server
    try:
        remote_addr = environ['REMOTE_ADDR']
    except KeyError:
        remote_addr = None
    try:
        remote_host = environ['REMOTE_HOST']
    except KeyError:
        remote_host = None
    params = FieldStorage(environ['wsgi.input'], environ=environ)

    # Call main server
    cookie_hdrs, response_data = serve(params, remote_addr, remote_host)
    # Then package and send response
   
    # Not returning 200 OK is a breach of protocol with the client
    response_code = '200 OK'
    # Add the cookie data if we have any
    if cookie_hdrs is not None:
        response_hdrs = [hdr for hdr in cookie_hdrs]
    else:
        response_hdrs = []
    response_hdrs.extend(response_data[0])

    start_response(response_code, response_hdrs)
    # Add a newline for readability
    return [response_data[1] + '\n']

if __name__ == '__main__':
    from sys import exit
    WSGIServer(stav_app).run()
    exit(0)
