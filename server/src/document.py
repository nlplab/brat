#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

# XXX: This module along with stats and annotator is pretty much pure chaos

from __future__ import with_statement

'''
Document handling functionality.

Author:     Pontus Stenetorp    <pontus is s u-tokyo ac jp>
Version:    2011-04-21
'''

from os import listdir
from os.path import abspath, isabs, isdir
from os.path import join as path_join
from re import sub

from annotation import Annotations, TEXT_FILE_SUFFIX
from annspec import span_type_keyboard_shortcuts
from config import DATA_DIR
from htmlgen import generate_client_keymap, generate_textbound_type_html
from projectconfig import ProjectConfiguration
from stats import get_statistics
from message import display_message

# Temporary catch while we phase in this part
try:
    from config import PERFORM_VERIFICATION
except ImportError:
    PERFORM_VERIFICATION = False

def real_directory(directory):
    assert isabs(directory), 'directory "%s" is not absolute' % directory
    return path_join(DATA_DIR, directory[1:])

def _is_hidden(file_name):
    return file_name.startswith('hidden_') or file_name.startswith('.')

def _listdir(directory):
    return listdir(directory)
    return [f for f in listdir(directory) if not _is_hidden(f)]

# TODO: This is not the prettiest of functions
def get_directory_information(directory):
    real_dir = real_directory(directory)

    # Get the document names
    base_names = [fn[0:-4] for fn in _listdir(real_dir)
            if fn.endswith('txt')]

    doclist = base_names[:]
    doclist_header = [("Document", "string")]

    # Then get the modification times
    from os.path import getmtime, join
    doclist_with_time = []
    for file in doclist:
        try:
            from annotation import JOINED_ANN_FILE_SUFF
            mtime = getmtime(join(DATA_DIR,
                join(real_dir, file + "." + JOINED_ANN_FILE_SUFF)))
        except OSError:
            # The file did not exist (or similar problem)
            mtime = -1
        doclist_with_time.append([file, mtime])
    doclist = doclist_with_time
    doclist_header.append(("Modified", "time"))

    doc_stats = get_statistics(real_dir)
                
    doclist = [doclist[i] + doc_stats[i] for i in range(len(doclist))]
    doclist_header += [("Textbounds", "int"), ("Events", "int")]

    dirlist = [dir for dir in _listdir(real_dir)
            if isdir(path_join(real_dir, dir))]
    # just in case, and for generality
    dirlist = [[dir] for dir in dirlist]

    if real_dir != DATA_DIR:
        parent = abspath(path_join(real_dir, '..'))[len(DATA_DIR) + 1:]
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
    html = generate_textbound_type_html(real_dir, span_type_keyboard_shortcuts)

    # we need a ProjectConfiguration for the abbrevs here. This could be
    # shared with htmlgen, which also needs one.
    projectconfig = ProjectConfiguration(real_dir)
    abbrevs = projectconfig.get_abbreviations()

    json_dic = {
            'docs': combolist,
            'dochead' : doclist_header,
            'parent': parent,
            'messages': [],
            'keymap': client_keymap,
            'abbrevs': abbrevs,
            'html': html,
            }
    return json_dic

#TODO: All this enrichment isn't a good idea, at some point we need an object
def _enrich_json_with_text(j_dic, txt_file_path):
    j_dic['text'] = _sentence_split(txt_file_path)

def _enrich_json_with_data(j_dic, ann_obj):
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
        error_msg = 'Unable to parse the following line(s):<br/>%s' % (
                '\n<br/>\n'.join(
                    [('%s: %s' % (
                        # The line number is off by one
                        str(line_num + 1),
                        str(ann_obj[line_num])
                        )).strip()
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

def _enrich_json_with_base(j_dic):
    # TODO: Make the names here and the ones in the Annotations object conform
    # This is the from offset
    j_dic['offset'] = 0
    j_dic['entities'] = []
    j_dic['events'] = []
    j_dic['triggers'] = []
    j_dic['modifications'] = []
    j_dic['equivs'] = []
    j_dic['infos'] = []

def _document_json_dict(document):
    #TODO: DOC!

    j_dic = {}
    _enrich_json_with_base(j_dic)

    #TODO: We don't check if the files exist, let's be more error friendly
    # Read in the textual data to make it ready to push
    _enrich_json_with_text(j_dic, document + '.' + TEXT_FILE_SUFFIX)

    with Annotations(document) as ann_obj:
        _enrich_json_with_data(j_dic, ann_obj)

    return j_dic

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

def get_document(directory, document):
    real_dir = real_directory(directory)
    doc_path = path_join(real_dir, document)
    return _document_json_dict(doc_path)

# From the old ajax server
'''
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
<link rel="stylesheet" type="text/css" href="style.css"/>
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
'''
