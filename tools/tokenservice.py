#!/usr/bin/env python

"""A very simple tokenization service."""

import re
from argparse import ArgumentParser
from cgi import FieldStorage
from http.server import BaseHTTPRequestHandler, HTTPServer
from sys import stderr

try:
    from json import dumps
except ImportError:
    # likely old Python; try to fall back on ujson in brat distrib
    from sys import path as sys_path
    from os.path import join as path_join
    from os.path import dirname
    sys_path.append(path_join(dirname(__file__), '../server/lib/ujson'))
    from ujson import dumps

try:
    pass
except ImportError:
    # old Python again?
    pass

# Constants
ARGPARSER = ArgumentParser(description='An trivial tokenization service')
ARGPARSER.add_argument('-p', '--port', type=int, default=47111,
                       help='port to run the HTTP service on (default: 47111)')
###


def _tokens(text):
    # Generate Token annotations
    anns = {}
    if not text:
        # We got no text, bail
        return anns

    offset, aseq = 0, 1
    for token in re.split('(\s+)', text):
        if token and not token.isspace():
            anns['T%d' % aseq] = {
                'type': 'Token',
                'offsets': ((offset, offset + len(token)), ),
                'texts': (token, ),
            }
            aseq += 1
        offset += len(token)
    return anns


class TokenizerHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        field_storage = FieldStorage(
            headers=self.headers,
            environ={
                'REQUEST_METHOD': 'POST',
                'CONTENT_TYPE': self.headers['Content-type'],
            },
            fp=self.rfile)

        # Do your random tagging magic
        try:
            json_dic = _tokens(field_storage.value.decode('utf-8'))
        except KeyError:
            # We weren't given any text to tag, such is life, return nothing
            json_dic = {}

        # Write the response
        self.send_response(200)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()

        self.wfile.write(dumps(json_dic))
        print(('Generated %d tokens' % len(json_dic)), file=stderr)

    def log_message(self, format, *args):
        return  # Too much noise from the default implementation


def main(args):
    argp = ARGPARSER.parse_args(args[1:])

    server_class = HTTPServer
    httpd = server_class(('localhost', argp.port), TokenizerHandler)
    print('Tokenizer service started on port %s' % (argp.port), file=stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    print('Tokenizer service stopped', file=stderr)


if __name__ == '__main__':
    from sys import argv
    exit(main(argv))
