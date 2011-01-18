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

# Arguments allowed for events, by type. Derived from the tables on
# the per-task pages under http://sites.google.com/site/bionlpst/ .

# abbrevs
theme_only_argument = {
    "Theme" : ["Protein"],
    }

theme_and_site_arguments = {
    "Theme" : ["Protein"],
    "Site"  : ["Entity"],
}

regulation_arguments = {
    "Theme" : ["Protein", "event"],
    "Cause" : ["Protein", "event"],
    "Site"  : ["Entity"],
    "CSite" : ["Entity"],
    }

localization_arguments = {
    "Theme" : ["Protein"],
    "AtLoc" : ["Entity"],
    "ToLoc" : ["Entity"],
    }

sidechain_modification_arguments = {
    "Theme"     : ["Protein"],
    "Site"      : ["Entity"],
    "Sidechain" : ["Entity"],
    }

contextgene_modification_arguments = {
    "Theme"       : ["Protein"],
    "Site"        : ["Entity"],
    "Contextgene" : ["Protein"],
    }

event_argument_types = {
    # GENIA
    "default"             : theme_only_argument,
    "Phosphorylation"     : theme_and_site_arguments,
    "Localization"        : localization_arguments,
    "Binding"             : theme_and_site_arguments,
    "Regulation"          : regulation_arguments,
    "Positive_regulation" : regulation_arguments,
    "Negative_regulation" : regulation_arguments,

    # EPI
    "Dephosphorylation"   : theme_and_site_arguments,
    "Hydroxylation"       : theme_and_site_arguments,
    "Dehydroxylation"     : theme_and_site_arguments,
    "Ubiquitination"      : theme_and_site_arguments,
    "Deubiquitination"    : theme_and_site_arguments,
    "DNA_methylation"     : theme_and_site_arguments,
    "DNA_demethylation"   : theme_and_site_arguments,
    "Glycosylation"       : sidechain_modification_arguments,
    "Deglycosylation"     : sidechain_modification_arguments,
    "Acetylation"         : contextgene_modification_arguments,
    "Deacetylation"       : contextgene_modification_arguments,
    "Methylation"         : contextgene_modification_arguments,
    "Demethylation"       : contextgene_modification_arguments,
    "Catalysis"           : regulation_arguments,

    # TODO: ID
    }

def is_physical_entity_type(t):
    return t in physical_entity_types

def is_event_type(t):
    # TODO: this assumption may not always hold, check properly
    return not is_physical_entity_type(t)

def possible_arc_types_from_to(from_ann, to_ann):
    if is_physical_entity_type(from_ann):
        # only possible "outgoing" edge from a physical entity is Equiv
        # to another entity of the same type.
        if from_ann == to_ann:
            return ["Equiv"]
        else:
            return []
    elif is_event_type(from_ann):
        # look up the big table
        args = event_argument_types.get(from_ann, event_argument_types["default"])

        possible = []
        for a in args:
            if (to_ann in args[a] or
                is_event_type(to_ann) and "event" in args[a]):
                possible.append(a)
        return possible
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
            "infos" : [],
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
        elif tag == "#":
            # comment (i.e. info). Comments formatted as "#\tTYPE ID[\tSTRING]"
            # can be displayed on the visualization; others will be ignored.
            fields = line.split("\t")
            if len(fields) > 1:
                f2 = fields[1].split(" ")
                if len(f2) == 2:
                    ctype, cid = f2
                    comment = ""
                    if len(fields) > 2:
                        comment = fields[2]
                    struct["infos"].append([cid, ctype, comment])
            
    triggers = triggers.keys()
    struct["triggers"] = [entity for entity in struct["entities"] if entity[0] in triggers]
    struct["entities"] = [entity for entity in struct["entities"] if entity[0] not in triggers]
    struct["error"] = None
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

    possible = possible_arc_types_from_to(origin_type, target_type)

    response = { "types" : [], "message" : None }

    # TODO: proper error handling
    if possible is None:
        response["message"] = "Error selecting arc types!"
    elif possible == []:
        response["message"] = "No choices for %s -> %s" % (origin_type, target_type)
    else:
        response["types"]   = [["Arcs", possible]]
        
    print dumps(response, sort_keys=True, indent=2)

def save_span(document, spanfrom, spanto, spantype, negation,
        speculation, id):
    # if id present: edit
    # if spanfrom and spanto present, new
    print "Content-Type: text/html\n"
    print "Added", document, spanfrom, spanto, spantype, negation, speculation, id # TODO do something with it

def save_arc(document, arcorigin, arctarget, arctype):
    # (arcorigin, arctarget) is unique
    # if exists before, replace
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
                        params.getvalue('type'),
                        params.getvalue('negation') == 'true',
                        params.getvalue('speculation') == 'true',
                        params.getvalue('id'))
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
