#!/usr/bin/env python

'''
Run brat using the built-in Python CGI server for testing purposes.

Author:     Pontus Stenetorp    <pontus stenetorp se>
Version:    2012-07-01
'''

from BaseHTTPServer import HTTPServer, test as simple_http_server_test
from CGIHTTPServer import CGIHTTPRequestHandler
# Note: It is a terrible idea to import the function below, but we don't have
#   a choice if we want to emulate the super-class is_cgi method.
from CGIHTTPServer import _url_collapse_path_split
from sys import stderr
from urlparse import urlparse

# Note: The only reason that we sub-class in order to pull is the stupid
#   is_cgi method that assumes the usage of specific CGI directories, I simply
#   refuse to play along with this kind of non-sense.
class BRATCGIHTTPRequestHandler(CGIHTTPRequestHandler):
    def is_cgi(self):
        # Having a CGI suffix is really a big hint of being a CGI script.
        if urlparse(self.path).path.endswith('.cgi'):
            self.cgi_info = _url_collapse_path_split(self.path)
            return True
        else:
            return CGIHTTPRequestHandler.is_cgi(self)

def main(args):
    # BaseHTTPServer will look for the port in argv[1] or default to 8000
    try:
        try:
            port = int(args[1])
        except ValueError:
            raise TypeError
    except TypeError:
        print >> stderr, '%s is not a valid port number' % args[1]
        return -1
    except IndexError:
        port = 8000
    print >> stderr, 'WARNING: This server is for testing purposes only!'
    print >> stderr, ('    You can also use it for trying out brat before '
            'deploying on a "real" web server such as Apache.')
    print >> stderr, ('    Using this web server to run brat on an open '
            'network is a security risk!')
    print >> stderr
    print >> stderr, 'You can access the test server on:'
    print >> stderr
    print >> stderr, '    http://localhost:%s/' % port
    print >> stderr
    simple_http_server_test(BRATCGIHTTPRequestHandler, HTTPServer)

if __name__ == '__main__':
    from sys import argv
    exit(main(argv))
