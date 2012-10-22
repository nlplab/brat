#!/usr/bin/env python

# Minimal standalone brat server based on CGIHTTPRequestHandler.

# Run as apache, e.g. as
#     sudo -u www-data python standalone.py

import sys
import os

from posixpath import normpath
from urllib import unquote

from cgi import FieldStorage
from BaseHTTPServer import HTTPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler
from SocketServer import ForkingMixIn
from CGIHTTPServer import CGIHTTPRequestHandler

# brat imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'server/src'))
from server import serve

# pre-import everything possible (TODO: prune unnecessary)
import annlog
import annotation
import annotator
import auth
import common
import delete
import dispatch
import docimport
import document
import download
import filelock
import gtbtokenize
import jsonwrap
import message
import normdb
import norm
import predict
import projectconfig
import realmessage
import sdistance
import search
import server
import session
import simstringdb
import sosmessage
import ssplit
import sspostproc
import stats
import svg
import tag
import tokenise
import undo
import verify_annotations

_SERVER_ADDR = ''
_SERVER_PORT = 8001

_PERMISSIONS = """
Disallow: *.py
Disallow: *.cgi
Disallow: /.htaccess
Disallow: *.py~  # no emacs backups
Disallow: *.cgi~
Disallow: /.htaccess~
Allow: /
"""

class PermissionParseError(Exception):
    def __init__(self, linenum, line, message=None):
        self.linenum = linenum
        self.line = line
        self.message = ' (%s)' % message if message is not None else ''
    
    def __str__(self):
        return 'line %d%s: %s' % (self.linenum, self.message, self.line)

class PathPattern(object):
    def __init__(self, path):
        self.path = path
        self.plen = len(path)

    def match(self, s):
        # Require prefix match and separator/end.
        return s[:self.plen] == self.path and (self.path[-1] == '/' or
                                               s[self.plen:] == '' or 
                                               s[self.plen] == '/')

class ExtensionPattern(object):
    def __init__(self, ext):
        self.ext = ext

    def match(self, s):
        return os.path.splitext(s)[1] == self.ext

class PathPermissions(object):
    """Implements path permission checking with a robots.txt-like syntax."""

    def __init__(self, default_allow=False):
        self._entries = []
        self.default_allow = default_allow

    def allow(self, path):
        # First match wins
        for pattern, allow in self._entries:
            if pattern.match(path):
                return allow
        return self.default_allow
    
    def parse(self, lines):
        # Syntax: "DIRECTIVE : PATTERN" where
        # DIRECTIVE is either "Disallow:" or "Allow:" and
        # PATTERN either has the form "*.EXT" or "/PATH".
        # Strings starting with "#" and empty lines are ignored.

        for ln, l in enumerate(lines):            
            i = l.find('#')
            if i != -1:
                l = l[:i]
            l = l.strip()

            if not l:
                continue

            i = l.find(':')
            if i == -1:
                raise PermissionParseError(ln, lines[ln], 'missing colon')

            directive = l[:i].strip().lower()
            pattern = l[i+1:].strip()

            if directive == 'allow':
                allow = True
            elif directive == 'disallow':
                allow = False
            else:
                raise PermissionParseError(ln, lines[ln], 'unrecognized directive')
            
            if pattern.startswith('/'):
                patt = PathPattern(pattern)
            elif pattern.startswith('*.'):
                patt = ExtensionPattern(pattern[1:])
            else:
                raise PermissionParseError(ln, lines[ln], 'unrecognized pattern')

            self._entries.append((patt, allow))

        return self

class BratHTTPRequestHandler(CGIHTTPRequestHandler):
    """Minimal handler for brat server."""

    permissions = PathPermissions().parse(_PERMISSIONS.split('\n'))

    def is_brat(self):
        if self.path == '/ajax.cgi':
            return True
        else:
            return False    

    def run_brat_direct(self):
        """Execute brat server directly."""

        # following ajax.cgi

        remote_addr = self.client_address[0]
        remote_host = self.address_string()
        cookie_data = ', '.join(filter(None, self.headers.getheaders('cookie')))

        saved = sys.stdin, sys.stdout, sys.stderr
        sys.stdin, sys.stdout = self.rfile, self.wfile

        # set env to get FieldStorage to read params from STDIN
        env = {}
        env['REQUEST_METHOD'] = 'POST'
        env['CONTENT_LENGTH'] = self.headers.getheader('content-length')
        os.environ.update(env)
        params = FieldStorage()

        # Call main server
        cookie_hdrs, response_data = serve(params, remote_addr, remote_host,
                                           cookie_data)

        sys.stdin, sys.stdout, sys.stderr = saved

        # Package and send response
        if cookie_hdrs is not None:
            response_hdrs = [hdr for hdr in cookie_hdrs]
        else:
            response_hdrs = []
        response_hdrs.extend(response_data[0])

        self.send_response(200)
        self.wfile.write('\n'.join('%s: %s' % (k, v) for k, v in response_hdrs))
        self.wfile.write('\n')
        self.wfile.write('\n')
        # Hack to support binary data and general Unicode for SVGs and JSON
        if isinstance(response_data[1], unicode):
            self.wfile.write(response_data[1].encode('utf-8'))
        else:
            self.wfile.write(response_data[1])
        return 0

    def run_brat_exec(self):
        """Execute brat server using execfile('ajax.cgi')."""

        # stipped down from CGIHTTPRequestHandler run_cgi()

        scriptfile = self.translate_path('/ajax.cgi')

        env = {}
        env['REQUEST_METHOD'] = 'POST'
        env['REMOTE_HOST'] = self.address_string()
        env['REMOTE_ADDR'] = self.client_address[0]
        env['CONTENT_LENGTH'] = self.headers.getheader('content-length')
        env['HTTP_COOKIE'] = ', '.join(filter(None, self.headers.getheaders('cookie')))
        os.environ.update(env)

        self.send_response(200)

        try:
            saved = sys.stdin, sys.stdout, sys.stderr
            sys.stdin, sys.stdout = self.rfile, self.wfile
            sys.argv = [scriptfile]
            try:
                execfile(scriptfile, {'__name__': '__main__',
                                      '__file__': __file__ })
            finally:
                sys.stdin, sys.stdout, sys.stderr = saved
        except SystemExit, sts:
            print >> sys.stderr, 'exit status', sts
        else:
            print >> sys.stderr, 'exit OK'

    def allow_path(self):
        """Test whether to allow a request for self.path."""

        # Cleanup in part following SimpleHTTPServer.translate_path()
        path = self.path
        path = path.split('?', 1)[0]
        path = path.split('#', 1)[0]
        path = unquote(path)
        path = normpath(path)
        parts = path.split('/')
        parts = filter(None, parts)
        if '..' in parts:
            return False
        path = '/'+'/'.join(parts)

        return self.permissions.allow(path)

    def list_directory(self, path):
        """Override SimpleHTTPRequestHandler.list_directory()"""
        # TODO: permissions for directory listings
        self.send_error(403)

    def do_POST(self):
        """Serve a POST request. Only implemented for brat server."""

        if self.is_brat():
            self.run_brat_direct()
        else:
            self.send_error(501, "Can only POST to brat")

    def do_GET(self):
        """Serve a GET request."""
        if not self.allow_path():
            self.send_error(403)
        else:
            CGIHTTPRequestHandler.do_GET(self)

    def do_HEAD(self):
        """Serve a HEAD request."""
        if not self.allow_path():
            self.send_error(403)
        else:
            CGIHTTPRequestHandler.do_HEAD(self)
       
class BratServer(ForkingMixIn, HTTPServer):
    def __init__(self, server_address):
        HTTPServer.__init__(self, server_address, BratHTTPRequestHandler)

def main(argv):
    try:
        server = BratServer((_SERVER_ADDR, _SERVER_PORT))
        server.serve_forever()
    except:
        print >> sys.stderr, "Server error"
        raise
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
