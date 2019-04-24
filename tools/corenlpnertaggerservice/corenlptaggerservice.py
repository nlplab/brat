#!/usr/bin/env python

"""Simple tagger service using CoreNLP.

Author:     Pontus Stenetorp    <pontus stenetorp se>
Version:    2012-04-18
"""

from argparse import ArgumentParser
from cgi import FieldStorage
from http.server import BaseHTTPRequestHandler, HTTPServer
from os.path import join as path_join
from os.path import dirname
from sys import stderr

from corenlp import CoreNLPTagger

try:
    from json import dumps
except ImportError:
    # likely old Python; try to fall back on ujson in brat distrib
    from sys import path as sys_path
    sys_path.append(path_join(dirname(__file__), '../../server/lib/ujson'))
    from ujson import dumps


# Constants
ARGPARSER = ArgumentParser(description='XXX')  # XXX:
ARGPARSER.add_argument('-p', '--port', type=int, default=47111,
                       help='port to run the HTTP service on (default: 47111)')
TAGGER = None
# XXX: Hard-coded!
CORENLP_PATH = path_join(dirname(__file__), 'stanford-corenlp-2012-04-09')
###


class CoreNLPTaggerHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        print('Received request', file=stderr)
        field_storage = FieldStorage(
            headers=self.headers,
            environ={
                'REQUEST_METHOD': 'POST',
                'CONTENT_TYPE': self.headers['Content-Type'],
            },
            fp=self.rfile)

        global TAGGER
        json_dic = TAGGER.tag(field_storage.value)

        # Write the response
        self.send_response(200)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()

        self.wfile.write(dumps(json_dic))
        print(('Generated %d annotations' % len(json_dic)), file=stderr)

    def log_message(self, format, *args):
        return  # Too much noise from the default implementation


def main(args):
    argp = ARGPARSER.parse_args(args[1:])

    print("WARNING: Don't use this in a production environment!", file=stderr)

    print('Starting CoreNLP process (this takes a while)...', end=' ', file=stderr)
    global TAGGER
    TAGGER = CoreNLPTagger(CORENLP_PATH)
    print('Done!', file=stderr)

    server_class = HTTPServer
    httpd = server_class(('localhost', argp.port), CoreNLPTaggerHandler)
    print('CoreNLP tagger service started', file=stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    print('CoreNLP tagger service stopped', file=stderr)


if __name__ == '__main__':
    from sys import argv
    exit(main(argv))
