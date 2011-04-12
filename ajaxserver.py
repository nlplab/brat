#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Ajax server called upon by the CGI to serve requests to the service.

Author:     Sampo   Pyysalo     <smp is s u tokyo ac jp>
Author:     Pontus  Stenetorp   <pontus is s u tokyo ac jp>
Author:     Goran   Topic       <goran is s u tokyo ac jp>
Version:    2010-01-24
'''

#TODO: Move imports into their respective functions to boost load time
from session import Session
from cgi import FieldStorage
from itertools import chain
from json import dumps, loads
from os import environ
from os import listdir, makedirs, system
from os.path import isdir, isfile, abspath
from os.path import join as join_path
from os.path import split as split_path
from re import split, sub, match
import fileinput
import hashlib

from annotation import Annotations, TEXT_FILE_SUFFIX, AnnotationsIsReadOnly
from annspec import span_type_keyboard_shortcuts
from backup import backup
from projectconfig import ProjectConfiguration
from verify_annotations import verify_annotation
# We should not import this in the end...
from annotation import (TextBoundAnnotation, EquivAnnotation,
        EventAnnotation, ModifierAnnotation, DependingAnnotationDeleteError)
from message import display_message, add_messages_to_json

### Constants?
EDIT_ACTIONS = ['span', 'arc', 'unspan', 'unarc', 'logout', 'import', 'confirm', 'runtagger']
COOKIE_ID = 'brat-cred'

# Add new configuration variables here
#TODO: We really should raise an exception to ajax.cgi to give a nicer message
#       if these configurations are wrong.
from config import BASE_DIR, DATA_DIR, USER_PASSWORD, DEBUG
try:
    from config import PERFORM_VERIFICATION
except ImportError:
    # reasonable default
    PERFORM_VERIFICATION = True

# XXX TODO: replace this quick ugly hack with an invocation through
# the interface we designed for taggers
def tag_file(directory, document):
    import os
    textfn      = os.path.join(DATA_DIR, directory, document+'.txt')
    tagger_root = os.path.join(BASE_DIR, '../nlpwrap')
    tagger_cmd  = os.path.join(tagger_root, 'tag-NERsuite.sh')+" "+textfn
    try:
        os.system(tagger_cmd)
    except Exception, e:
        display_message("Error: failed to run tagger. Please contact the administrator(s).", "error", -1)
        from sys import stderr
        print >> stderr, e
        return
    taggedfn    = os.path.join(tagger_root, 'output', document+'.ner')

    # read in tagged, mark everything with AnnotationUnconfirmed
    import re
    try:
        f = open(taggedfn)
        outputlines = []
        next_comment_id = 1
        for l in f:
            m = re.match(r'^(T\d+)\t(\S+) (\d+) (\d+)\t(.*)', l)
            assert m, "Failed to parse tagger output line '%s'" % l
            tid, ttype, start, end, ttext = m.groups()
            # worse hack in bad hack: rename type
            if ttype == "Protein":
                ttype = "Gene_or_gene_product"
            l = "%s\t%s %s %s\t%s\n" % (tid, ttype, start, end, ttext)
            outputlines.append(l)
            outputlines.append('#%d\tAnnotationUnconfirmed %s\tAutomatically generated annotation, please confirm by clicking\n' % (next_comment_id, tid))
            next_comment_id += 1
        f.close()
    except Exception, e:
        display_message("Error: failed to read tagger output. Please contact the administrator(s).", "error", -1)
        from sys import stderr
        print >> stderr, e
        return

    # XXX TODO: incorporate via Annotation object
    # first-attempt hack: clobber the existing .ann
    try:
        annfn = os.path.join(DATA_DIR, directory, document+'.ann')
        f = open(annfn, 'wt')
        for l in outputlines:
            f.write(l)
        f.close()
    except Exception, e:
        display_message("Error: failed to store tagger output. Please contact the administrator(s).", "error", -1)
        from sys import stderr
        print >> stderr, e
        return

def my_listdir(directory):
    return [l for l in listdir(directory)
            # XXX: A hack to remove what we don't want to be seen
            if not (l.startswith('hidden_') or l.startswith('.'))]

def export(directory, real_directory):
    from urllib import quote
    from cgi import escape

    try:
        doclist = [file[0:-4] for file in my_listdir(real_directory)
                if file.endswith('txt')]
        doclist.sort()

        edir = escape(directory)
        qdir = quote(directory)
        print """Content-Type: text/html

<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"> 
<html>
<head>
<title>%s - brat</title>
<link rel="stylesheet" type="text/css" href="annotator.css"/>
</head>
<body id="export_page">
<img id="logo" src="brat-logo.png"/>
<div><strong>Documents in directory %s</strong></div>
<table>
""" % (edir, edir)
        background = 0
        for file in doclist:
            efile = escape(file)
            qfile = quote(file)

            print """<tr class="background%d">
<th>%s</th>
<td><a href="ajax.cgi?action=fetch&amp;directory=%s&amp;document=%s.txt">Text</a></td>
<td><a href="ajax.cgi?action=fetch&amp;directory=%s&amp;document=%s.ann">Annotations</a></td>
</tr>
""" % (background, efile, qdir, qfile, qdir, qfile)
            background = 1-background

        print """</table>
</body>
</html>
"""

    except OSError, x:
        print "Content-Type: text/html"
        print "Status: 404 File Not Found\n"

def fetch(real_directory, document):
    try:
        print "Content-Type: text/plain\n"
        with open(join_path(real_directory, document)) as f:
            print f.read()
    except OSError, x:
        print "Content-Type: text/html\n"
        print "Status: 404 File Not Found\n"

def documents(directory):
    # TODO: this function combines up unrelated functionality; split

    from htmlgen import generate_textbound_type_html, generate_client_keymap
    print 'Content-Type: application/json\n'
    try:
        basenames = [file[0:-4] for file in my_listdir(directory)
                     if file.endswith('txt')]

        doclist   = basenames[:]
        doclist_header = [("Document", "string")]

        from os.path import getmtime, join
        doclist_with_time = []
        for file in doclist:
            try:
                from annotation import JOINED_ANN_FILE_SUFF
                mtime = getmtime(join(DATA_DIR,
                    join(directory, file+"."+JOINED_ANN_FILE_SUFF)))
            except OSError:
                # The file did not exist (or similar problem)
                mtime = -1
            doclist_with_time.append([file, mtime])
        doclist = doclist_with_time
        doclist_header.append(("Modified", "time"))

        # TODO: replace this costly hack with an implementation that
        # caches statistics
        docstats = []
        for docname in basenames:
            try:
                # TODO: didn't work as Annotations(docname) although
                # (if I understand correctly) it should. Check
#                 with Annotations(docname, read_only=True) as ann_obj:
                from annotation import JOINED_ANN_FILE_SUFF
                with Annotations(join(DATA_DIR, join(directory, docname+"."+JOINED_ANN_FILE_SUFF)), read_only=True) as ann_obj:
                    tb_count = len([a for a in ann_obj.get_textbounds()])
                    event_count = len([a for a in ann_obj.get_events()])
                    docstats.append([tb_count, event_count])
            except:
                docstats.append(["(no stats)", "(no stats)"])
        doclist = [doclist[i] + docstats[i] for i in range(len(doclist))]
        doclist_header += [("Textbounds", "int"), ("Events", "int")]

        dirlist = [dir for dir in my_listdir(directory)
                if isdir(join_path(directory, dir))]
        # just in case, and for generality
        dirlist = [[dir] for dir in dirlist]

        if directory != DATA_DIR:
            parent = abspath(join_path(directory, '..'))[len(DATA_DIR) + 1:]
            # to get consistent processing client-side, add explicitly to list
            dirlist.append([".."])
        else:
            parent = None

        # combine document and directory lists, adding a column
        # differentiating files from directories (True for dir).
        combolist = []
        for i in dirlist:
            combolist.append([True]+i)
        for i in doclist:
            combolist.append([False]+i)

        client_keymap = generate_client_keymap(span_type_keyboard_shortcuts)
        html = generate_textbound_type_html(directory, span_type_keyboard_shortcuts)

        # we need a ProjectConfiguration for the abbrevs here. This could be
        # shared with htmlgen, which also needs one.
        projectconfig = ProjectConfiguration(directory)
        abbrevs = projectconfig.get_abbreviations()

        response = {
                'docs': combolist,
                'dochead' : doclist_header,
                'parent': parent,
                'messages': [],
                'keymap': client_keymap,
                'abbrevs': abbrevs,
                'html': html,
                }

    except OSError, e:
        if e.errno == 2:
            display_message('Error: No such directory: ' + directory, 'error', -1)
            response = { 'exception': 'InvalidDirectory' }
        else:
            raise

    add_messages_to_json(response)
    print dumps(response, sort_keys=True, indent=2)

def _sentence_split(txt_file_path):
    from geniass import sentence_split_file
    try:
        ret = sentence_split_file(txt_file_path, use_cache=True)
        # This ought to be the hack of the month, if we got nothing back,
        # fake an exception and fall into the heuristic. This happens for
        # linking errors among other things.
        if not ret:
            err = OSError()
            err.errno = 2
            raise err
        return ret
    except OSError, e:
        # If the file is not found we do an ugly fall-back, this is far
        # too general of an exception handling at the moment.
        if e.errno == 2:
            with open(txt_file_path, 'r') as txt_file:
                return sub(r'(\. *) ([A-Z])',r'\1\n\2', txt_file.read())
        else:
            raise

#TODO: All this enrichment isn't a good idea, at some point we need an object
def enrich_json_with_text(j_dic, txt_file_path):
    j_dic['text'] = _sentence_split(txt_file_path)

def enrich_json_with_data(j_dic, ann_obj):
    # We collect trigger ids to be able to link the textbound later on
    trigger_ids = set()
    for event_ann in ann_obj.get_events():
        trigger_ids.add(event_ann.trigger)
        j_dic['events'].append(
                [str(event_ann.id), str(event_ann.trigger), event_ann.args]
                )

    for tb_ann in ann_obj.get_textbounds():
        j_tb = [str(tb_ann.id), tb_ann.type, tb_ann.start, tb_ann.end]

        # If we spotted it in the previous pass as a trigger for an
        # event or if the type is known to be an event type, we add it
        # as a json trigger.
        # TODO: proper handling of disconnected triggers. Currently
        # these will be erroneously passed as 'entities'
        if str(tb_ann.id) in trigger_ids:
            j_dic['triggers'].append(j_tb)
        else: 
            j_dic['entities'].append(j_tb)

    for eq_ann in ann_obj.get_equivs():
        j_dic['equivs'].append(
                (['*', eq_ann.type]
                    + [e for e in eq_ann.entities])
                )

    for mod_ann in ann_obj.get_modifers():
        j_dic['modifications'].append(
                [str(mod_ann.id), mod_ann.type, mod_ann.target]
                )

    for com_ann in ann_obj.get_oneline_comments():
        j_dic['infos'].append(
                [com_ann.target, com_ann.type, com_ann.tail.strip()]
                )

    if ann_obj.failed_lines:
        error_msg = 'Unable to parse the following line(s):<br/>{0}'.format(
                '\n<br/>\n'.join(
                    ['{0}: {1}'.format(
                        # The line number is off by one
                        str(line_num + 1),
                        str(ann_obj[line_num])
                        ).strip()
                    for line_num in ann_obj.failed_lines])
                    )
        display_message(error_msg, type='error', duration=len(ann_obj.failed_lines) * 3)

    j_dic['mtime'] = ann_obj.ann_mtime
    j_dic['ctime'] = ann_obj.ann_ctime

    try:
        # XXX avoid digging the directory from the ann_obj
        if PERFORM_VERIFICATION:
            import os
            docdir = os.path.dirname(ann_obj._document)
            projectconfig = ProjectConfiguration(docdir)
            issues = verify_annotation(ann_obj, projectconfig)
        else:
            issues = []
    except Exception, e:
        # TODO add an issue about the failure?
        issues = []
        display_message('Error: verify_annotation() failed: %s' % e, 'error', -1)

    for i in issues:
        j_dic['infos'].append((str(i.ann_id), i.type, i.description))

def enrich_json_with_base(j_dic):
    # TODO: Make the names here and the ones in the Annotations object conform
    # This is the from offset
    j_dic['offset'] = 0
    j_dic['entities'] = []
    j_dic['events'] = []
    j_dic['triggers'] = []
    j_dic['modifications'] = []
    j_dic['equivs'] = []
    j_dic['infos'] = []

def document_json_dict(document):
    #TODO: DOC!

    j_dic = {}
    enrich_json_with_base(j_dic)

    #TODO: We don't check if the files exist, let's be more error friendly
    # Read in the textual data to make it ready to push
    enrich_json_with_text(j_dic, document + '.' + TEXT_FILE_SUFFIX)

    with Annotations(document) as ann_obj:
        enrich_json_with_data(j_dic, ann_obj)

    return j_dic

def document_json(docdir, docname):
    document = join_path(docdir, docname)
    j_dic = document_json_dict(document)
    print 'Content-Type: application/json\n'
    add_messages_to_json(j_dic)
    print dumps(j_dic, sort_keys=True, indent=2)

def saveSVGReal(svgPath, cssPath, svg):
    file = open(svgPath, 'wb')
    file.write('<?xml version="1.0" standalone="no"?><!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">')
    defs = svg.find('</defs>')
    if defs != -1:
        css = open(cssPath).read()
        css = '<style type="text/css"><![CDATA[' + css + ']]></style>'
        svg = svg[:defs] + css + svg[defs:]
        file.write(svg)
        file.close()
        # system('rsvg %s.svg %s.png' % (basename, basename))
    else:
        display_message("Error: bad SVG!", "error", -1)

def saveSVG(directory, document, svg):
    dir = '/'.join([BASE_DIR, 'svg', directory])
    if not isdir(dir):
        makedirs(dir)
    basename = dir + '/' + document
    svgPath = basename + '.svg'
    cssPath = BASE_DIR + '/annotator.css'
    saveSVGReal(svgPath, cssPath, svg)

    response = { }
    print 'Content-Type: application/json\n'
    add_messages_to_json(response)
    print dumps(response, sort_keys=True, indent=2)

def saveSVGForUser(user, svg):
    dir = '/'.join([BASE_DIR, 'svg', 'user'])
    if not isdir(dir):
        makedirs(dir)
    basename = dir + '/' + user

    cssPath = BASE_DIR + '/annotator.css'
    saveSVGReal(basename + '_color.svg', BASE_DIR + '/annotator.css', svg)
    saveSVGReal(basename + '_grayscale.svg', BASE_DIR + '/annotator_grayscale.css', svg)

    response = { }
    print 'Content-Type: application/json\n'
    add_messages_to_json(response)
    print dumps(response, sort_keys=True, indent=2)

def downloadSVGForUser(user, document, version):
    dir = '/'.join([BASE_DIR, 'svg', 'user'])
    basename = dir + '/' + user
    svgPath = basename + '_' + version + '.svg'
    print 'Content-Type: image/svg+xml'
    print 'Content-Disposition: inline; filename=' + document + '.svg\n'
    print open(svgPath).read()


def arc_types_html(projectconfig, origin_type, target_type):
    response = { }

    # TODO: this should likely go into htmlgen
    try:
        possible = projectconfig.arc_types_from_to(origin_type, target_type)

        # TODO: proper error handling
        if possible is None:
            display_message("Error selecting arc types!", "error", -1)
        elif possible == []:
            # nothing to select
            response['html'] = "<fieldset><legend>Type</legend>(No valid arc types)</fieldset>"
            response['keymap'] = {}
            response['empty'] = True
        else:
            # pick hotkeys
            key_taken = {}
            key_for   = {}
            response['keymap']  = { }
            for p in possible:
                for i in range(len(p)):
                    if p[i].lower() not in key_taken:
                        key_taken[p[i].lower()] = True
                        key_for[p] = p[i].lower()
                        response['keymap'][p[i].upper()] = "arc_"+p.lower()
                        break

            # generate input for each possible choice
            inputs = []
            for p in possible:
                inputstr = '<input id="arc_%s" type="radio" name="arc_type" value="%s"/>' % (p.lower().replace(" ","_"),p)
                if p not in key_for:
                    inputstr += '<label for="arc_%s">%s</label>' % (p.lower().replace(" ","_"), p)
                else:
                    accesskey = key_for[p]
                    key_offset= p.lower().find(accesskey)
                    inputstr += '<label for="arc_%s">%s<span class="accesskey">%s</span>%s</label>' % (p.lower().replace(" ","_"), p[:key_offset], p[key_offset:key_offset+1], p[key_offset+1:])
                inputs.append(inputstr)
            response['html']  = '<fieldset><legend>Type</legend>' + '\n'.join(inputs) + '</fieldset>'
    except:
        display_message("Error selecting arc types!", "error", -1)
        raise
    
    print 'Content-Type: application/json\n'
    add_messages_to_json(response)
    print dumps(response, sort_keys=True, indent=2)

#TODO: Couldn't we incorporate this nicely into the Annotations class?
#TODO: Yes, it is even gimped compared to what it should do when not. This
#       has been a long pending goal for refactoring.
class ModificationTracker(object):
    def __init__(self):
        self.__added = []
        self.__changed = []
        self.__deleted = []

    def __len__(self):
        return len(self.__added) + len(self.__changed) + len(self.__deleted)

    def addition(self, added):
        self.__added.append(added)

    def deletion(self, deleted):
        self.__deleted.append(deleted)

    def change(self, before, after):
        self.__changed.append((before, after))

    def json_response(self, response=None):
        if response is None:
            response = {}

        # debugging
        msg_str = ''
        if self.__added:
            msg_str += ('Added the following line(s):\n<br/>'
                    + '\n<br/>\n'.join([str(a) for a in self.__added]))
        if self.__changed:
            changed_strs = []
            for before, after in self.__changed:
                changed_strs.append('\t{0}\n<br/>\n\tInto:\n<br/>\t{1}'.format(before, after))
            msg_str += ('Changed the following line(s):\n<br/>'
                    + '\n<br/>\n'.join([str(a) for a in changed_strs]))
        if self.__deleted:
            msg_str += ('Deleted the following line(s):\n<br/>'
                    + '\n<br/>\n'.join([str(a) for a in self.__deleted]))
        if msg_str:
            display_message(msg_str, duration=3*len(self))
        else:
            display_message('No changes made')

        # highlighting
        response['edited'] = []
        # TODO: implement cleanly, e.g. add a highlightid() method to Annotation classes
        for a in self.__added:
            try:
                response['edited'].append(a.reference_id())
            except AttributeError:
                pass # not all implement reference_id()
        for b,a in self.__changed:
            # can't mark "before" since it's stopped existing
            try:
                response['edited'].append(a.reference_id())
            except AttributeError:
                pass # not all implement reference_id()

        return response

def confirm_span(docdir, docname, span_id):
    document = join_path(docdir, docname)

    txt_file_path = document + '.' + TEXT_FILE_SUFFIX

    with Annotations(document) as ann_obj:
        mods = ModificationTracker()

        # find AnnotationUnconfirmed comments that refer
        # to the span and remove them
        # TODO: error checking
        for ann in ann_obj.get_oneline_comments():
            if ann.type == "AnnotationUnconfirmed" and ann.target == span_id:
                ann_obj.del_annotation(ann, mods)

        print 'Content-Type: application/json\n'
        if DEBUG:
            mods_json = mods.json_response()
        else:
            mods_json = {}
        # save a roundtrip and send the annotations also
        txt_file_path = document + '.' + TEXT_FILE_SUFFIX
        j_dic = json_from_ann_and_txt(ann_obj, txt_file_path)
        mods_json["annotations"] = j_dic
        add_messages_to_json(mods_json)
        print dumps(mods_json, sort_keys=True, indent=2)


#TODO: ONLY determine what action to take! Delegate to Annotations!
def save_span(docdir, docname, start_str, end_str, type, negation, speculation, id):
    #TODO: Handle the case when negation and speculation both are positive
    # if id present: edit
    # if spanfrom and spanto present, new
    #XXX: Negation, speculation not done!

    document = join_path(docdir, docname)

    projectconfig = ProjectConfiguration(docdir)

    txt_file_path = document + '.' + TEXT_FILE_SUFFIX

    working_directory = split_path(document)[0]

    with Annotations(document) as ann_obj:
        mods = ModificationTracker()

        if id is not None:
            #TODO: Handle failure to find!
            ann = ann_obj.get_ann_by_id(id)
            
            # Hack to support event annotations
            try:
                if int(start_str) != ann.start or int(end_str) != ann.end:
                    # This scenario has been discussed and changing the span inevitably
                    # leads to the text span being out of sync since we can't for sure
                    # determine where in the data format the text (if at all) it is
                    # stored. For now we will fail loudly here.
                    print 'Content-Type: application/json\n'
                    error_msg = 'unable to change the span of an existing annotation'
                    display_message(error_msg, type='error', duration=3)
                    print dumps(add_messages_to_json({}), sort_keys=True, indent=2)
                    # Not sure if we only get an internal server error or the data
                    # will actually reach the client to be displayed.
                    assert False, error
                    
                    # Span changes are as of yet unsupported
                    #ann.start = start
                    #ann.end = end
            except AttributeError:
                 # It is most likely an event annotion
                pass

            if ann.type != type:
                if projectconfig.type_category(ann.type) != projectconfig.type_category(type):
                    display_message("Cannot convert %s (%s) into %s (%s)" % (ann.type, projectconfig.type_category(ann.type), type, projectconfig.type_category(type)), "error", -1)
                    pass
                else:
                    before = str(ann)
                    ann.type = type

                    # Try to propagate the type change
                    try:
                        #XXX: We don't take into consideration other anns with the
                        # same trigger here!
                        ann_trig = ann_obj.get_ann_by_id(ann.trigger)
                        if ann_trig.type != ann.type:
                            # At this stage we need to determine if someone else
                            # is using the same trigger
                            if any((event_ann
                                for event_ann in ann_obj.get_events()
                                if (event_ann.trigger == ann.trigger
                                        and event_ann != ann))):
                                # Someone else is using it, create a new one
                                from copy import copy
                                # A shallow copy should be enough
                                new_ann_trig = copy(ann_trig)
                                # It needs a new id
                                new_ann_trig.id = ann_obj.get_new_id('T')
                                # And we will change the type
                                new_ann_trig.type = ann.type
                                # Update the old annotation to use this trigger
                                ann.trigger = str(new_ann_trig.id)
                                ann_obj.add_annotation(new_ann_trig)
                                mods.addition(new_ann_trig)
                            else:
                                # Okay, we own the current trigger, but does an
                                # identical to our sought one already exist?
                                found = None
                                for tb_ann in ann_obj.get_textbounds():
                                    if (tb_ann.start == ann_trig.start
                                            and tb_ann.end == ann_trig.end
                                            and tb_ann.type == ann.type):
                                        found = tb_ann
                                        break

                                if found is None:
                                    # Just change the trigger type since we are the
                                    # only users

                                    before = str(ann_trig)
                                    ann_trig.type = ann.type
                                    mods.change(before, ann_trig)
                                else:
                                    # Attach the new trigger THEN delete
                                    # or the dep will hit you
                                    ann.trigger = str(found.id)
                                    ann_obj.del_annotation(ann_trig)
                                    mods.deletion(ann_trig)
                    except AttributeError:
                        # It was most likely a TextBound entity
                        pass

                    # Finally remember the change
                    mods.change(before, ann)
            # Here we assume that there is at most one of each in the file, this can be wrong
            seen_spec = None
            seen_neg = None
            for other_ann in ann_obj:
                try:
                    if other_ann.target == str(ann.id):
                        if other_ann.type == 'Speculation': #XXX: Cons
                            seen_spec = other_ann
                        if other_ann.type == 'Negation': #XXX: Cons
                            seen_neg = other_ann
                except AttributeError:
                    pass
            # Is the attribute set and none existing? Add.
            if speculation and seen_spec is None:
                spec_mod_id = ann_obj.get_new_id('M') #XXX: Cons
                spec_mod = ModifierAnnotation(str(ann.id), str(spec_mod_id),
                        'Speculation', '') #XXX: Cons
                ann_obj.add_annotation(spec_mod)
                mods.addition(spec_mod)
            if negation and seen_neg is None:
                neg_mod_id = ann_obj.get_new_id('M') #XXX: Cons
                neg_mod = ModifierAnnotation(str(ann.id), str(neg_mod_id),
                        'Negation', '') #XXX: Cons
                ann_obj.add_annotation(neg_mod)
                mods.addition(neg_mod)
            # Is the attribute unset and one existing? Erase.
            if not speculation and seen_spec is not None:
                try:
                    ann_obj.del_annotation(seen_spec)
                    mods.deletion(seen_spec)
                except DependingAnnotationDeleteError:
                    assert False, 'Dependant attached to speculation'
            if not negation and seen_neg is not None:
                try:
                    ann_obj.del_annotation(seen_neg)
                    mods.deletion(seen_neg)
                except DependingAnnotationDeleteError:
                    assert False, 'Dependant attached to negation'

            # It could be the case that the span is involved in event(s), if so, 
            # the type of that event is changed
            #TODO:
        else:
            start = int(start_str)
            end = int(end_str)

            # Before we add a new trigger, does it already exist?
            found = None
            for tb_ann in ann_obj.get_textbounds():
                try:
                    if (tb_ann.start == start and tb_ann.end == end
                            and tb_ann.type == type):
                        found = tb_ann
                        break
                except AttributeError:
                    # Not a trigger then
                    pass

            if found is None:
                # Get a new ID
                new_id = ann_obj.get_new_id('T') #XXX: Cons
                # Get the text span
                with open(txt_file_path, 'r') as txt_file:
                    txt_file.seek(start)
                    text = txt_file.read(end - start)
                        
                #TODO: Data tail should be optional
                if '\n' not in text:
                    ann = TextBoundAnnotation(start, end, new_id, type, '\t' + text)
                    ann_obj.add_annotation(ann)
                    mods.addition(ann)
                else:
                    ann = None
            else:
                ann = found

            if ann is not None:
                if projectconfig.is_physical_entity_type(type):
                    # TODO: alert that negation / speculation are ignored if set
                    pass
                else:
                    # Create the event also
                    new_event_id = ann_obj.get_new_id('E') #XXX: Cons
                    event = EventAnnotation(ann.id, [], str(new_event_id), type, '')
                    ann_obj.add_annotation(event)
                    mods.addition(event)

                    # TODO: use an existing identical textbound for the trigger
                    # if one exists, don't dup            

                    if speculation:
                        spec_mod_id = ann_obj.get_new_id('M') #XXX: Cons
                        spec_mod = ModifierAnnotation(str(new_event_id),
                                str(spec_mod_id), 'Speculation', '') #XXX: Cons
                        ann_obj.add_annotation(spec_mod)
                        mods.addition(spec_mod)
                    else:
                        neg_mod = None
                    if negation:
                        neg_mod_id = ann_obj.get_new_id('M') #XXX: Cons
                        neg_mod = ModifierAnnotation(str(new_event_id),
                                str(neg_mod_id), 'Negation', '') #XXX: Cons
                        ann_obj.add_annotation(neg_mod)
                        mods.addition(neg_mod)
                    else:
                        neg_mod = None
            else:
                # We got a newline in the span, don't take any action
                pass

        print 'Content-Type: application/json\n'
        if ann is not None:
            if DEBUG:
                mods_json = mods.json_response()
            else:
                mods_json = {}
        else:
            # Hack, we had a new-line in the span
            mods_json = {}
            display_message('Text span contained new-line, rejected',
                    type='error', duration=3)
        # save a roundtrip and send the annotations also
        txt_file_path = document + '.' + TEXT_FILE_SUFFIX
        j_dic = json_from_ann_and_txt(ann_obj, txt_file_path)
        mods_json['annotations'] = j_dic

        add_messages_to_json(mods_json)
        print dumps(mods_json, sort_keys=True, indent=2)
           
#TODO: Should determine which step to call next
def save_arc(docdir, docname, origin, target, type, old_type):
    mods = ModificationTracker()

    document = join_path(docdir, docname)

    with Annotations(document) as ann_obj:
        origin, target = ann_obj.get_ann_by_id(origin), ann_obj.get_ann_by_id(target)

        # Ugly check, but we really get no other information
        if type != 'Equiv':
            try:
                arg_tup = (type, str(target.id))
                if old_type is None:
                    old_arg_tup = None
                else:
                    old_arg_tup = (old_type, str(target.id))

                if old_arg_tup is None:
                    if arg_tup not in origin.args:
                        before = str(origin)
                        origin.args.append(arg_tup)
                        mods.change(before, origin)
                    else:
                        # It already existed as an arg, we were called to do nothing...
                        pass
                else:
                    if old_arg_tup in origin.args and arg_tup not in origin.args:
                        before = str(origin)
                        origin.args.remove(old_arg_tup)
                        origin.args.append(arg_tup)
                        mods.change(before, origin)
                    else:
                        # Collision etc. don't do anything
                        pass
            except AttributeError:
                # The annotation did not have args, it was most likely an entity
                # thus we need to create a new Event...
                new_id = ann_obj.get_new_id('E')
                ann = EventAnnotation(
                            origin.id,
                            [arg_tup],
                            new_id,
                            origin.type,
                            ''
                            )
                ann_obj.add_annotation(ann)
                mods.addition(ann)
        else:
            # It is an Equiv
            if old_type == "Equiv":
                # "Change" from Equiv to Equiv is harmless
                # TODO: some message needed?
                pass
            else:
                assert old_type is None, 'attempting to change Equiv, not supported'
                ann = EquivAnnotation(type, [str(origin.id), str(target.id)], '')
                ann_obj.add_annotation(ann)
                mods.addition(ann)

        print 'Content-Type: application/json\n'
        if DEBUG:
            mods_json = mods.json_response()
        else:
            mods_json = {}

        # Hack since we don't have the actual text, should use a factory?
        txt_file_path = ann_obj.get_document() + '.' + TEXT_FILE_SUFFIX
        j_dic = json_from_ann_and_txt(ann_obj, txt_file_path)

        mods_json['annotations'] = j_dic
        add_messages_to_json(mods_json)
        print dumps(mods_json, sort_keys=True, indent=2)

# Hack for the round-trip
def json_from_ann_and_txt(ann_obj, txt_file_path):
    j_dic = {}
    enrich_json_with_base(j_dic)
    enrich_json_with_text(j_dic, txt_file_path)
    enrich_json_with_data(j_dic, ann_obj)
    return j_dic


#TODO: ONLY determine what action to take! Delegate to Annotations!
def delete_span(docdir, docname, id):
    document = join_path(docdir, docname)
    
    txt_file_path = document + '.' + TEXT_FILE_SUFFIX

    with Annotations(document) as ann_obj:
        mods = ModificationTracker()
        
        #TODO: Handle a failure to find it
        #XXX: Slow, O(2N)
        ann = ann_obj.get_ann_by_id(id)
        try:
            # Note: need to pass the tracker to del_annotation to track
            # recursive deletes. TODO: make usage consistent.
            ann_obj.del_annotation(ann, mods)
            try:
                trig = ann_obj.get_ann_by_id(ann.trigger)
                try:
                    ann_obj.del_annotation(trig, mods)
                except DependingAnnotationDeleteError:
                    # Someone else depended on that trigger
                    pass
            except AttributeError:
                pass
        except DependingAnnotationDeleteError, e:
            print 'Content-Type: application/json\n'
            display_message(e.html_error_str(), type='error', duration=3)
            print dumps(add_messages_to_json({}), sort_keys=True, indent=2)
            return

        print 'Content-Type: application/json\n'
        if DEBUG:
            mods_json = mods.json_response()
        else:
            mods_json = {}
        # save a roundtrip and send the annotations also
        txt_file_path = document + '.' + TEXT_FILE_SUFFIX
        j_dic = json_from_ann_and_txt(ann_obj, txt_file_path)
        mods_json["annotations"] = j_dic
        add_messages_to_json(mods_json)
        print dumps(mods_json, sort_keys=True, indent=2)

#TODO: ONLY determine what action to take! Delegate to Annotations!
def delete_arc(docdir, docname, origin, target, type):
    document = join_path(docdir, docname)

    txt_file_path = document + '.' + TEXT_FILE_SUFFIX

    with Annotations(document) as ann_obj:
        mods = ModificationTracker()

        # This can be an event or an equiv
        #TODO: Check for None!
        try:
            event_ann = ann_obj.get_ann_by_id(origin)
            # Try if it is an event
            arg_tup = (type, str(target))
            if arg_tup in event_ann.args:
                before = str(event_ann)
                event_ann.args.remove(arg_tup)
                mods.change(before, event_ann)

                '''
                if not event_ann.args:
                    # It was the last argument tuple, remove it all
                    try:
                        ann_obj.del_annotation(event_ann)
                        mods.deletion(event_ann)
                    except DependingAnnotationDeleteError, e:
                        #XXX: Old message api
                        print 'Content-Type: application/json\n'
                        print dumps(e.json_error_response(), sort_keys=True, indent=2)
                        return
                '''
            else:
                # What we were to remove did not even exist in the first place
                pass

        except AttributeError:
            # It is an equiv then?
            #XXX: Slow hack! Should have a better accessor! O(eq_ann)
            for eq_ann in ann_obj.get_equivs():
                # We don't assume that the ids only occur in one Equiv, we
                # keep on going since the data "could" be corrupted
                if (str(origin) in eq_ann.entities
                        and str(target) in eq_ann.entities):
                    before = str(eq_ann)
                    eq_ann.entities.remove(str(origin))
                    eq_ann.entities.remove(str(target))
                    mods.change(before, eq_ann)

                if len(eq_ann.entities) < 2:
                    # We need to delete this one
                    try:
                        ann_obj.del_annotation(eq_ann)
                        mods.deletion(eq_ann)
                    except DependingAnnotationDeleteError, e:
                        #TODO: This should never happen, dep on equiv
                        print 'Content-Type: application/json\n'
                        display_message(e.json_error_response(), type='error', duration=3)
                        print dumps(add_messages_to_json({}), sort_keys=True, indent=2)
                        return

        print 'Content-Type: application/json\n'
        if DEBUG:
            mods_json = mods.json_response()
        else:
            mods_json = {}
        # save a roundtrip and send the annotations also
        txt_file_path = document + '.' + TEXT_FILE_SUFFIX
        j_dic = json_from_ann_and_txt(ann_obj, txt_file_path)
        mods_json['annotations'] = j_dic
        add_messages_to_json(mods_json)
        print dumps(mods_json, sort_keys=True, indent=2)

class InvalidAuthException(Exception):
    pass

class SecurityViolationException(Exception):
    pass

def authenticate(login, password):
    # TODO: Database back-end
    if login not in USER_PASSWORD or password != hashlib.sha512(USER_PASSWORD[login]).hexdigest():
        raise InvalidAuthException()

def serve(argv):
    # Check for back-ups
    backup()

    params = FieldStorage()
    Session.instance = Session()
    
    user = Session.instance.get('user')

    directory = params.getvalue('directory')
    document = params.getvalue('document')

    action = params.getvalue('action')

    try:
        if action in EDIT_ACTIONS:
            if not user:
                print 'Content-Type: text/plain'
                print 'Status: 403 Forbidden (auth)\n'
                return

        if action == 'login':
            auth_dict = { }
            user = params.getvalue('user')
            password = hashlib.sha512(params.getvalue('pass')).hexdigest()

            try:
                authenticate(user, password)
                Session.instance['user'] = user
                display_message('Hello!')
            except InvalidAuthException:
                auth_dict['exception'] = 'denied'
                display_message('Incorrect login or password', 'error', 5)

            print 'Content-Type: application/json\n'
            add_messages_to_json(auth_dict)
            print dumps(auth_dict, sort_keys=True, indent=2)

        elif action == 'logout':
            Session.instance.invalidate()
            logout_dict = {}
            print 'Content-Type: application/json\n'
            display_message('Bye!')
            add_messages_to_json(logout_dict)
            print dumps(logout_dict, sort_keys=True, indent=2)

        elif action == 'getuser':
            result = {}
            try:
                result['user'] = Session.instance.get('user')
            except (KeyError):
                display_message('Not logged in!', type='error', duration=3)
            print 'Content-Type: application/json\n'
            print dumps(add_messages_to_json(result), sort_keys=True, indent=2)

        elif action == 'import':
            from docimport import save_import, FileExistsError
            doctext = params.getvalue('title')+"\n"+params.getvalue('text')
            import_dict = {}
            try:
                save_import(doctext, params.getvalue('docid'),
                            params.getvalue('directory'))
                import_dict['address'] = params.getvalue('docid')
            except FileExistsError:
                display_message('Cannot import: file exists', 'error', -1)
            print 'Content-Type: application/json\n'
            add_messages_to_json(import_dict)
            print dumps(import_dict, sort_keys=True, indent=2)

        elif action == 'runtagger':
            runtagger_dict = {}
            directory = params.getvalue('directory')
            document  = params.getvalue('document')
            tag_file(directory, document)
            display_message('Run tagger invoked for %s doc %s. TODO: implement server-side' % (directory, document))
            print 'Content-Type: application/json\n'
            add_messages_to_json(runtagger_dict)
            print dumps(runtagger_dict, sort_keys=True, indent=2)

        elif action == 'saveUserSVG':
            # FIXME
            # does not work for multiuser environment.
            # I want sessions!
            # otherwise, can't distinguish anonymous users.
            saveSVGForUser(Session.instance.sid, params.getvalue('svg'))

        elif action == 'downloadUserSVG':
            # FIXME
            # does not work for multiuser environment.
            # I want sessions!
            # otherwise, can't distinguish anonymous users.
            downloadSVGForUser(Session.instance.sid,
                    params.getvalue('document'),
                    params.getvalue('version'))

        else:
            if directory is None:
                directory = ''
            else:
                directory = directory.lstrip('/')
            real_directory = abspath(join_path(DATA_DIR, directory))
            data_abs = abspath(DATA_DIR)
            if not real_directory.startswith(data_abs):
                # FIXME: possible security breach, Pythonistas please fix:
                # "/foo/dataforbidden/securedir" directory would match "/foo/data" directory
                # is there a better way to determine subdirectoricity than:
                # dir.startswith(parent + '/') or dir == parent
                # (also, Pontus doesn't like me using '/')
                assert False, "DATA_DIR: " + DATA_DIR + "; data_abs: " + data_abs + "; real_directory: " + real_directory
                raise SecurityViolationException()

            if action == 'spantypes':
                # TODO: remove this once it's confirmed that there are no
                # attempts to use it
                display_message("Error: received 'spantypes' request; this is deprecated.", "error", -1)

            elif action == 'arctypes':
                projectconfig = ProjectConfiguration(real_directory)
                arc_types_html(
                    projectconfig,
                    params.getvalue('origin'),
                    params.getvalue('target')
                    )

            elif action == 'ls':
                documents(real_directory)

            elif action == 'export':
                export(directory, real_directory)

            else:
                if document.find('/') != -1:
                    raise SecurityViolationException()

                span = params.getvalue('span')
                #XXX: Calls to save and delete can raise AnnotationNotFoundError
                try:
                    if action == 'fetch':
                        fetch(real_directory, document)

                    elif action == 'span':
                        # TODO: proper interface for rapid mode span
                        spantype = params.getvalue('type')
                        if spantype == "GUESS":
                            from simsem import predict_sem_type
                            predicted = predict_sem_type(params.getvalue('spantext'))
                            display_message("<br/>".join(predicted))

                        save_span(real_directory, document,
                                params.getvalue('from'),
                                params.getvalue('to'),
                                params.getvalue('type'),
                                params.getvalue('negation') == 'true',
                                params.getvalue('speculation') == 'true',
                                params.getvalue('id'))
                    elif action == 'arc':
                        save_arc(real_directory, document,
                                params.getvalue('origin'),
                                params.getvalue('target'),
                                params.getvalue('type'),
                                params.getvalue('old') or None)
                    elif action == 'unspan':
                        delete_span(real_directory, document,
                                params.getvalue('id'))
                    elif action == 'unarc':
                        delete_arc(real_directory, document,
                                params.getvalue('origin'),
                                params.getvalue('target'),
                                params.getvalue('type'))
                    elif action == 'confirmspan':
                        confirm_span(real_directory, document,
                                     params.getvalue('span'))
                    elif action == 'save':
                        svg = params.getvalue('svg')
                        saveSVG(directory, document, svg)
                    else:
                        document_json(real_directory, document)
                except IOError, e:
                    #TODO: This is too general, should be caught at a higher level
                    # No such file or directory
                    response = {}
                    if e.errno == 2:
                        display_message('Error: file not found', 'error', -1)
                        response['exception'] = 'FileNotFound'
                    else:
                        display_message('Error: I/O error opening file', 'error', -1)

                    print 'Content-Type: application/json\n'
                    add_messages_to_json(response)
                    print dumps(response, sort_keys=True, indent=2)

                except AnnotationsIsReadOnly:
                    display_message('Error: server lacks permission to write the '
                                    '.ann annotations file, please contact '
                                    'the administrator(s)', 'error', -1)

                    print 'Content-Type: application/json\n'
                    response = {}
                    add_messages_to_json(response)
                    print dumps(response, sort_keys=True, indent=2)
    except SecurityViolationException, e:
        print 'Content-Type: text/plain'
        print 'Status: 403 Forbidden (path)\n'
        return



def debug():
    from os.path import dirname, join

    debug_file_path = join('BioNLP-ST_2011_Epi_and_PTM_development_data', 'PMID-10086714')
    dirname = dirname(__file__)

    args = (dirname,
            debug_file_path,
        '59',
        '74',
        'Protein',
        False,
        False,
        None
        )
    save_span(*args)

    '''
    args = (debug_file_path,
        'T31',
        )
    delete_span(*args)
    '''

    args = (dirname,
            debug_file_path,
        'T5',
        'T4',
        'Equiv',
        None
        )
    save_arc(*args)
    
    args = (dirname,
            debug_file_path,
        'E2',
        'T10',
        'Theme',
        None
        )
    save_arc(*args)

    args = args[:-1] 
    delete_arc(*args)


if __name__ == '__main__':
    # Rather ugly debug invocation
    if argv[1] == '-d':
        exit(debug())
