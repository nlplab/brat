#!/usr/bin/python

from cgi import FieldStorage
from os import listdir, makedirs, system
from os.path import isdir, isfile
from re import split, sub, match
from simplejson import dumps
from itertools import chain
import fileinput

basedir = '/data/home/genia/public_html/BioNLP-ST/visual'
datadir = basedir + '/data'

EDIT_ACTIONS = ['span', 'arc', 'unspan', 'unarc', 'auth']

physical_entity_types = [
    "Protein",
    "Entity",
    ]

event_role_types = [
    "Theme",
    "Cause",
    "Site",
    ]

def is_physical_entity_type(t):
    return t in physical_entity_types

def is_event_type(t):
    # TODO: this assumption may not always hold, check properly
    return not is_physical_entity_type(t)

def possible_arc_types_from(ann):
    """
    Returns a list of possible outgoing arc types from an annotation of
    the given type.
    """
    if is_physical_entity_type(ann):
        return ["Equiv"]
    elif is_event_type:
        return event_role_types
    else:
        return None

def possible_arc_types_to(ann):
    """
    Returns a list of possible ingoing arc types from an annotation of
    the given type.
    """
    if is_physical_entity_type(ann):
        # TODO: restrict by entity type
        return event_role_types + ["Equiv"]
    elif is_event_type(ann):
        # TODO: generalize
        return ["Theme", "Cause"]
    else:
        return None

def my_listdir(directory):
    return [l for l in listdir(directory)
            if not (l.startswith("hidden_") or l.startswith("."))]

def directory_options(directory):
    print "Content-Type: text/html\n"
    print "<option value=''>-- Select Document --</option>"
    dirlist = [file[0:-4] for file in my_listdir(directory)
            if file.endswith('txt')]
    dirlist.sort()
    for file in dirlist:
        print "<option>%s</option>" % file

def directories():
    print "Content-Type: text/html\n"
    print "<option value=''>-- Select Directory --</option>"
    dirlist = [dir for dir in my_listdir(datadir)]
    dirlist.sort()
    for dir in dirlist:
        print "<option>%s</option>" % dir

def document_json(document):
    print "Content-Type: application/json\n"
    from_offset = 0
    to_offset = None

    text = open(document + ".txt", "rb").read()
    text = sub(r'\. ([A-Z])',r'.\n\1', text)
    struct = {
            "offset": from_offset,
            "text": text,
            "entities": [],
            "events": [],
            "triggers": [],
            "modifications": [],
            "equivs": [],
            }

    triggers = dict()

    # iterate jointly over all present annotation files for the document
    foundfiles = [document+ext for ext in (".a1", ".a2", ".co", ".rel")
                  if isfile(document+ext)]
    if foundfiles:
        iter = fileinput.input(foundfiles)
    else:
        iter = []

    equiv_id = 1
    for line in iter:
        tag = line[0]
        row = [elem for elem in split('\s+', line) if elem != '']
        if tag == 'T':
            struct["entities"].append(row[0:4])
        elif tag == 'E':
            roles = [split(':', role) for role in row[1:] if role]

            triggers[roles[0][1]] = True
            # Ignore if no trigger
            if roles[0][1]:
                event = [row[0], roles[0][1], roles[1:]]
                struct["events"].append(event)
        elif tag == "M":
            struct["modifications"].append(row[0:3])
        elif tag == "R":
            # relation; fake as Equiv for now (TODO proper handling)
            m = match(r'^(\S+)\s+(\S+)\s+(\S+):(\S+)\s+(\S+):(\S+)\s*$', line)
            if m:
                rel_id, rel_type, e1_role, e1_id, e2_role, e2_id = m.groups()
                relann = ['*%s' % equiv_id] + [rel_type, e1_id, e2_id]
                struct["equivs"].append(relann)
                equiv_id += 1
            else:
                # TODO: error handling
                pass
        elif tag == "*":
            event = ['*%s' % equiv_id] + row[1:]
            struct["equivs"].append(event)
            equiv_id += 1
    triggers = triggers.keys()
    struct["triggers"] = [entity for entity in struct["entities"] if entity[0] in triggers]
    struct["entities"] = [entity for entity in struct["entities"] if entity[0] not in triggers]
    print dumps(struct, sort_keys=True, indent=2)


def saveSVG(directory, document, svg):
    dir = '/'.join([basedir, 'svg', directory])
    if not isdir(dir):
        makedirs(dir)
    basename = dir + '/' + document
    file = open(basename + '.svg', "wb")
    file.write('<?xml version="1.0" standalone="no"?><!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">')
    defs = svg.find('</defs>')
    if defs != -1:
        css = open(basedir + '/annotator.css').read()
        css = '<style type="text/css"><![CDATA[' + css + ']]></style>'
        svg = svg[:defs] + css + svg[defs:]
        file.write(svg)
        file.close()
        # system('rsvg %s.svg %s.png' % (basename, basename))
        print "Content-Type: application/json\n"
    else:
        print "Content-Type: text/plain"
        print "Status: 400 Bad Request\n"

def arc_types_html(origin_type, target_type):
    print "Content-Type: application/json\n"

    possible_from = possible_arc_types_from(origin_type)
    possible_to   = possible_arc_types_to(target_type)

    # TODO: proper error handling
    if possible_from is None or possible_from is None:
        response = { "message" : "Error selecting arc types!",
                     "types"   : [] }
    else:
        possible = [ t for t in possible_from if t in possible_to ]
        
        # TODO: proper labeling / grouping (i.e. not just "Arc")
        response = { "types" : [["Arcs", possible]] }
        if possible == []:
            response["message"] = "No choices for %s -> %s" % (origin_type, target_type)

    print dumps(response, sort_keys=True, indent=2)

def save_span(document, spanfrom, spanto, spantype):
    print "Content-Type: text/html\n"
    print "Added", document, spanfrom, spanto, spantype # TODO do something with it

def save_arc(document, arcorigin, arctarget, arctype):
    print "Content-Type: text/html\n"
    print "Added", document, arcorigin, arctarget, arctype # TODO do something with it

def delete_span(document, spanid):
    print "Content-Type: text/html\n"
    print "Deleted", document, spanid # TODO do something with it

def delete_arc(document, arcorigin, arctarget, arctype):
    print "Content-Type: text/html\n"
    print "Deleted", document, arcorigin, arctarget, arctype # TODO do something with it

def authenticate(login, password):
    # TODO
    return (login == 'editor' and password == 'crunchy')

def main():
    params = FieldStorage()
    directory = params.getvalue('directory')
    document = params.getvalue('document')

    if directory is None:
        input = ''
    elif document is None:
        input = directory
    else:
        input = directory + document
    if input.find('/') != -1:
        print "Content-Type: text/plain"
        print "Status: 403 Forbidden (slash)\n"
        return

    action = params.getvalue('action')
    if action in EDIT_ACTIONS:
        user = params.getvalue('user')
        if not authenticate(user, params.getvalue('pass')):
            print "Content-Type: text/plain"
            print "Status: 403 Forbidden (auth)\n"
            return

    if directory is None:
        if action == 'auth':
            print "Content-Type: text/plain\n"
            print "Hello, %s" % user
        elif action == 'arctypes':
            arc_types_html(
                params.getvalue('origin'),
                params.getvalue('target'))
        else:
            directories()
    else:
        directory = datadir + '/' + directory

        if document is None:
            if action == 'save':
                svg = params.getvalue('svg')
                saveSVG(directory, document, svg)
            else:
                directory_options(directory)
        else:
            docpath = directory + '/' + document
            span = params.getvalue('span')

            if action == 'span':
                save_span(docpath,
                        params.getvalue('from'),
                        params.getvalue('to'),
                        params.getvalue('type'))
            elif action == 'arc':
                save_arc(docpath,
                        params.getvalue('origin'),
                        params.getvalue('target'),
                        params.getvalue('type'))
            elif action == 'unspan':
                delete_span(docpath,
                        params.getvalue('id'))
            elif action == 'unarc':
                delete_arc(docpath,
                        params.getvalue('origin'),
                        params.getvalue('target'),
                        params.getvalue('type'))
            else:
                document_json(docpath)

main()
