#!/usr/bin/env python

# Minimal standalone brat server based on CGIHTTPRequestHandler.

# Run as apache, e.g. as
#     sudo -u www-data python standalone.py

import sys
import os

from BaseHTTPServer import HTTPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler
from SocketServer import ForkingMixIn
from CGIHTTPServer import CGIHTTPRequestHandler

# brat imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'server/src'))
from server import serve

_SERVER_ADDR = ''
_SERVER_PORT = 8001

class BratHTTPRequestHandler(CGIHTTPRequestHandler):
    """Minimal handler for brat server."""

    def is_brat(self):
        print self.path
        if self.path == '/ajax.cgi':
            return True
        else:
            return False    

    def run_brat(self):
        """Execute brat server."""

        # stipped down from CGIHTTPRequestHandler run_cgi()

        scriptname = '/ajax.cgi'
        scriptfile = self.translate_path(scriptname)

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

    def do_POST(self):
        """Serve a POST request. Only implemented for brat server."""

        if self.is_brat():
            self.run_brat()
        else:
            self.send_error(501, "Can only POST to brat")

    def allow_path(self):
        # TODO
        return True

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
