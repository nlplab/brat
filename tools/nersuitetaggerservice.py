#!/usr/bin/env python

'''
An example of a tagging service using NER suite.
'''

from argparse import ArgumentParser

from os.path import join as path_join
from os.path import dirname

try:
    from json import dumps
except ImportError:
    # likely old Python; try to fall back on ujson in brat distrib
    from sys import path as sys_path
    sys_path.append(path_join(dirname(__file__), '../server/lib/ujson'))
    from ujson import dumps

from subprocess import PIPE, Popen

from random import choice, randint
from sys import stderr
from urlparse import urlparse
try:
    from urlparse import parse_qs
except ImportError:
    # old Python again?
    from cgi import parse_qs
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
import re

# use the brat sentence splitter
from sentencesplit import sentencebreaks_to_newlines

# and use this hack for converting BIO to standoff
from BIOtoStandoff import BIO_lines_to_standoff

### Constants
DOCUMENT_BOUNDARY = 'END-DOCUMENT'
NERSUITE_SCRIPT   = path_join(dirname(__file__), './nersuite_tag.sh')
NERSUITE_COMMAND  = [NERSUITE_SCRIPT, '-multidoc', DOCUMENT_BOUNDARY]

ARGPARSER = ArgumentParser(description='An example HTTP tagging service using NERsuite')
ARGPARSER.add_argument('-p', '--port', type=int, default=47111,
        help='port to run the HTTP service on (default: 47111)')
###

### Globals
tagger_process = None

def run_tagger(cmd):
    # runs the tagger identified by the given command.
    global tagger_process
    try:
        tagger_process = Popen(cmd, stdin=PIPE, stdout=PIPE, bufsize=1)
    except Exception, e:
        print >> stderr, "Error running '%s':" % cmd, e
        raise

def _apply_tagger(text):
    global tagger_process, tagger_queue

    # the tagger expects a sentence per line, so do basic splitting
    try:
        splittext = sentencebreaks_to_newlines(text)
    except:
        # if anything goes wrong, just go with the
        # original text instead
        print >> stderr, "Warning: sentence splitting failed for input:\n'%s'" % text
        splittext = text

    print >> tagger_process.stdin, splittext
    print >> tagger_process.stdin, DOCUMENT_BOUNDARY
    tagger_process.stdin.flush()

    response_lines = []
    while True:
        l = tagger_process.stdout.readline()
        l = l.rstrip('\n')
        
        if l == DOCUMENT_BOUNDARY:
            break

        response_lines.append(l)
        
    try:
        tagged_entities = BIO_lines_to_standoff(response_lines, text)
    except:
        # if anything goes wrong, bail out
        print >> stderr, "Warning: BIO-to-standoff conversion failed for BIO:\n'%s'" % '\n'.join(response_lines)
        return {}

    anns = {}

    for t in tagged_entities:
        anns["T%d" % t.idNum] = {
            'type': t.eType,
            'offsets': ((t.startOff, t.endOff), ),
            'texts': (t.eText, ),
            }

    return anns

class NERsuiteTaggerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Get our query
        query = parse_qs(urlparse(self.path).query)

        try:
            json_dic = _apply_tagger(query['text'][0])
        except KeyError:
            # We weren't given any text to tag, such is life, return nothing
            json_dic = {}

        # Write the response
        self.send_response(200)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()

        self.wfile.write(dumps(json_dic))
        print >> stderr, ('Generated %d annotations' % len(json_dic))

    def log_message(self, format, *args):
        return # Too much noise from the default implementation

def main(args):
    argp = ARGPARSER.parse_args(args[1:])

    print >> stderr, 'Starting NERsuite ...'
    run_tagger(NERSUITE_COMMAND)

    server_class = HTTPServer
    httpd = server_class(('localhost', argp.port), NERsuiteTaggerHandler)

    print >> stderr, 'NERsuite tagger service started'
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    print >> stderr, 'NERsuite tagger service stopped'

if __name__ == '__main__':
    from sys import argv
    exit(main(argv))
