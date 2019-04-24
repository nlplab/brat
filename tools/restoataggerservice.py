#!/usr/bin/env python

"""An example of a tagging service using RESTful Open Annotation."""

import logging
import re
import sys
from cgi import FieldStorage
from http.server import BaseHTTPRequestHandler, HTTPServer
from json import dumps
from logging import info, warn

import requests

TAGGER_URI = 'http://tagger.jensenlab.org/OpenAnnotation'

DEFAULT_PORT = 47111

logging.basicConfig(level=logging.DEBUG)


def argparser():
    import argparse
    parser = argparse.ArgumentParser(
        description='HTTP tagging service using RESTful Open Annotation')
    parser.add_argument('-p', '--port', type=int, default=DEFAULT_PORT,
                        help='run service on PORT (default %d)' % DEFAULT_PORT)
    return parser


def _apply_tagger(text):
    r = requests.post(TAGGER_URI, data={'document': text})
    return r.json()


def _target_to_offset(target):
    m = re.match(r'^.*?\#char=(\d+),(\d+)$', target)
    start, end = m.groups()
    return int(start), int(end)


def _split_ref(ref):
    return ref.split(':', 1)


def _oa_to_ann(data, text):
    anns = {}
    nidx = 1
    for i, a in enumerate(data['@graph']):
        start, end = _target_to_offset(a['target'])
        # textbound
        anns['T%d' % (i + 1)] = {
            'type': 'Entity',
            'offsets': ((start, end), ),
            'texts': (text[start:end], ),
        }
        # normalization(s)
        bodies = a['body'] if isinstance(a['body'], list) else [a['body']]
        for b in bodies:
            refdb, refid = _split_ref(b['@id'])
            anns['N%d' % (nidx)] = {
                'type': 'Reference',
                'target': 'T%d' % (i + 1),
                'refdb': refdb,
                'refid': refid,
            }
            nidx += 1
    return anns


class RestOATaggerHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        fields = FieldStorage(headers=self.headers,
                              environ={
                                  'REQUEST_METHOD': 'POST',
                                  'CONTENT_TYPE': self.headers['Content-type'],
                              },
                              fp=self.rfile)
        try:
            text = fields.value.decode('utf-8')
        except KeyError:
            warn('query did not contain text')
            text = ''
        data = _apply_tagger(text)
        info(data)
        anns = _oa_to_ann(data, text)

        # Write the response
        self.send_response(200)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()

        self.wfile.write(dumps(anns))
        info('Generated %d annotations' % len(anns))


def main(argv):
    args = argparser().parse_args(argv[1:])

    httpd = HTTPServer(('localhost', args.port), RestOATaggerHandler)
    info('REST-OA tagger service started')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    info('REST-OA tagger service stopped')
    httpd.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
