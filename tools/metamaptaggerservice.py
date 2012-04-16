#!/usr/bin/env python

'''
An example of a tagging service using metamap.
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

# use this MetaMap output converter
from MetaMaptoStandoff import MetaMap_lines_to_standoff

### Constants
METAMAP_SCRIPT   = path_join(dirname(__file__), './metamap_tag.sh')
METAMAP_COMMAND  = [METAMAP_SCRIPT]

ARGPARSER = ArgumentParser(description='An example HTTP tagging service using MetaMap')
ARGPARSER.add_argument('-p', '--port', type=int, default=47111,
        help='port to run the HTTP service on (default: 47111)')
###

def run_tagger(cmd):
    # runs the tagger identified by the given command.
    try:
        tagger_process = Popen(cmd, stdin=PIPE, stdout=PIPE, bufsize=1)
        return tagger_process
    except Exception, e:
        print >> stderr, "Error running '%s':" % cmd, e
        raise    

def _apply_tagger_to_sentence(text):
    # can afford to restart this on each invocation
    tagger_process = run_tagger(METAMAP_COMMAND)

    print >> tagger_process.stdin, text
    tagger_process.stdin.close()
    tagger_process.wait()

    response_lines = []

    for l in tagger_process.stdout:
        l = l.rstrip('\n')
        response_lines.append(l)
        
    try:
        tagged_entities = MetaMap_lines_to_standoff(response_lines, text)
    except:
        # if anything goes wrong, bail out
        print >> stderr, "Warning: MetaMap-to-standoff conversion failed for output:\n'%s'" % '\n'.join(response_lines)
        raise
        #return {}

    # MetaMap won't echo matched text, so get this separately
    for t in tagged_entities:
        t.eText = text[t.startOff:t.endOff]

    return tagged_entities

def _apply_tagger(text):
    # MetaMap isn't too happy with large outputs, so process a
    # sentence per invocation

    try:
        splittext = sentencebreaks_to_newlines(text)
    except:
        # if anything goes wrong, just go with the
        # original text instead
        print >> stderr, "Warning: sentence splitting failed for input:\n'%s'" % text
        splittext = text

    sentences = splittext.split('\n')
    all_tagged = []
    baseoffset = 0
    for s in sentences:
        tagged = _apply_tagger_to_sentence(s)

        # adjust offsets
        for t in tagged:
            t.startOff += baseoffset
            t.endOff += baseoffset

        all_tagged.extend(tagged)
        baseoffset += len(s)+1

    anns = {}

    idseq = 1
    for t in all_tagged:
        anns["T%d" % idseq] = {
            'type': t.eType,
            'offsets': ((t.startOff, t.endOff), ),
            'texts': (t.eText, ),
            }
        idseq += 1

    return anns
        

class MetaMapTaggerHandler(BaseHTTPRequestHandler):
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

    print >> stderr, 'Starting MetaMap ...'

    server_class = HTTPServer
    httpd = server_class(('localhost', argp.port), MetaMapTaggerHandler)

    print >> stderr, 'MetaMap tagger service started'
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    print >> stderr, 'MetaMap tagger service stopped'

if __name__ == '__main__':
    from sys import argv
    exit(main(argv))
