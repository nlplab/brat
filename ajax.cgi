#!/usr/bin/python

from cgi import FieldStorage
from os import listdir, makedirs, system
from os.path import isdir
from re import split, sub
from simplejson import dumps
from itertools import chain

basedir = '/data/home/genia/public_html/BioNLP-ST/visual'
datadir = basedir + '/data'

def my_listdir(directory):
    return [l for l in listdir(directory) if "hidden_" not in l]

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
    iter = None
    try:
        iter = open(document + ".a1", "rb").readlines()
    except:
        pass
    try:
        moreiter = open(document + ".a2", "rb").readlines()
        iter = chain(iter, moreiter)
    except:
        iter = moreiter

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
        print "Status: 400 Bad Request\n"


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
        print "Status: 403 Forbidden\n"
        return

    savePassword = params.getvalue('save')
    if savePassword:
        if savePassword == 'crunchy':
            svg = params.getvalue('svg')
            saveSVG(directory, document, svg)
        else:
            print "Status: 403 Forbidden (password)\n\n"
    elif directory is None:
        directories()
    else:
        directory = datadir + '/' + directory

        if document is None:
            directory_options(directory)
        else:
            action = params.getvalue('action')
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
