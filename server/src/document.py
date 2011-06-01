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
from re import match,sub

from annotation import (TextAnnotations, TEXT_FILE_SUFFIX,
        AnnotationFileNotFoundError, open_textfile)
from common import ProtocolError
from config import DATA_DIR
from projectconfig import ProjectConfiguration, get_labels_by_storage_form
from stats import get_statistics
from message import display_message

# Temporary catch while we phase in this part
try:
    from config import PERFORM_VERIFICATION
except ImportError:
    PERFORM_VERIFICATION = False

# TODO: this is not a good spot for this
from itertools import chain

def _get_subtypes_for_type(nodes, project_conf, hotkey_by_type, directory):
    items = []
    for node in nodes:
        if node == 'SEPARATOR':
            items.append(None)
        else:
            item = {}
            _type = node.storage_form() 
            item['name'] = project_conf.preferred_display_form(_type)
            item['type'] = _type
            item['unused'] = node.unused
            item['labels'] = get_labels_by_storage_form(directory, _type)

            try:
                item['hotkey'] = hotkey_by_type[_type]
            except KeyError:
                pass

            arcs = {}
            for arc in chain(project_conf.relation_types_from(_type),
                    (a for a, _ in node.arguments)):
                arc_labels = get_labels_by_storage_form(directory, arc)

                if arc_labels is not None:
                    arcs[arc] = arc_labels
                    
            # If we found any arcs, attach them
            if arcs:
                item['arcs'] = arcs

            item['children'] = _get_subtypes_for_type(node.children,
                    project_conf, hotkey_by_type, directory)
            items.append(item)
    return items

# TODO: this may not be a good spot for this
def _get_attribute_type_info(nodes, project_conf, directory):
    items = []
    for node in nodes:
        if node == 'SEPARATOR':
            continue
        else:
            item = {}
            _type = node.storage_form() 
            item['name'] = project_conf.preferred_display_form(_type)
            item['type'] = _type
            item['unused'] = node.unused
            item['labels'] = get_labels_by_storage_form(directory, _type)

            # TODO: process "special" arguments (like <DEFAULT> and <GLYPH-POS>)
            glyph_pos = "left" # should read from <GLYPH-POS>

            # check if there are any (normal) "arguments"
            args = [(k,v) for k,v in node.arguments if k != "Arg" and not match(r'^<.*>$', k)]
            if len(args) == 0:
                # no, assume binary and mark accordingly
                # TODO: get rid of special cases, grab style from config
                if _type == 'Negation':
                    item['values'] = { _type : { 'box': u'crossed' } }
                else:
                    item['values'] = { _type : { 'dasharray': '3,3' } }
            else:
                # has normal arguments, use these as possible values
                item['values'] = {}
                for k,v in args:
                    item['values'][k] = { 'glyph':v, 'position':glyph_pos }
            items.append(item)
    return items

# TODO: this is not a good spot for this
def get_span_types(directory):
    project_conf = ProjectConfiguration(directory)

    keymap = project_conf.get_kb_shortcuts()
    hotkey_by_type = dict((v, k) for k, v in keymap.iteritems())

    event_hierarchy = project_conf.get_event_type_hierarchy()
    event_types = _get_subtypes_for_type(event_hierarchy,
            project_conf, hotkey_by_type, directory)

    entity_hierarchy = project_conf.get_entity_type_hierarchy()
    entity_types = _get_subtypes_for_type(entity_hierarchy,
            project_conf, hotkey_by_type, directory)

    attribute_hierarchy = project_conf.get_attribute_type_hierarchy()
    attribute_types = _get_attribute_type_info(attribute_hierarchy, project_conf, directory)

    relation_hierarchy = project_conf.get_relation_type_hierarchy()
    relation_types = _get_subtypes_for_type(relation_hierarchy,
            project_conf, hotkey_by_type, directory)

    return event_types, entity_types, attribute_types, relation_types

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
        except:
            # The file did not exist (or similar problem)
            mtime = -1
        doclist_with_time.append([file, mtime])
    doclist = doclist_with_time
    doclist_header.append(("Modified", "time"))

    doc_stats = get_statistics(real_dir, base_names)
                
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

    event_types, entity_types, attribute_types, relation_types = get_span_types(real_dir)

    json_dic = {
            'docs': combolist,
            'dochead' : doclist_header,
            'parent': parent,
            'messages': [],
            'event_types': event_types,
            'entity_types': entity_types,
            'attribute_types': attribute_types,
            'relation_types': relation_types,
            }
    return json_dic

class UnableToReadTextFile(ProtocolError):
    def __init__(self, path):
        self.path = path

    def json(self, json_dic):
        json_dic['exception'] = 'unableToReadTextFile'
        return json_dic

#TODO: All this enrichment isn't a good idea, at some point we need an object
def _enrich_json_with_text(j_dic, txt_file_path):
    try:
        j_dic['text'] = _sentence_split(txt_file_path)
        return True
    except IOError:
        raise UnableToReadTextFile(txt_file_path)

def _enrich_json_with_data(j_dic, ann_obj):
    # We collect trigger ids to be able to link the textbound later on
    trigger_ids = set()
    for event_ann in ann_obj.get_events():
        trigger_ids.add(event_ann.trigger)
        j_dic['events'].append(
                [unicode(event_ann.id), unicode(event_ann.trigger), event_ann.args]
                )

    for rel_ann in ann_obj.get_relations():
        j_dic['relations'].append(
            [unicode(rel_ann.id), unicode(rel_ann.type), rel_ann.arg1, rel_ann.arg2]
            )

    for tb_ann in ann_obj.get_textbounds():
        j_tb = [unicode(tb_ann.id), tb_ann.type, tb_ann.start, tb_ann.end]

        # If we spotted it in the previous pass as a trigger for an
        # event or if the type is known to be an event type, we add it
        # as a json trigger.
        # TODO: proper handling of disconnected triggers. Currently
        # these will be erroneously passed as 'entities'
        if unicode(tb_ann.id) in trigger_ids:
            j_dic['triggers'].append(j_tb)
        else: 
            j_dic['entities'].append(j_tb)

    for eq_ann in ann_obj.get_equivs():
        j_dic['equivs'].append(
                (['*', eq_ann.type]
                    + [e for e in eq_ann.entities])
                )

    # XXX: To be replaced by attributes
    for mod_ann in ann_obj.get_modifers():
        j_dic['modifications'].append(
                [unicode(mod_ann.id), mod_ann.type, mod_ann.target]
                )

    # Sending modifications as attributes to remain backwards compatible
    for mod_ann in ann_obj.get_modifers():
        j_dic['attributes'].append(
                [unicode(mod_ann.id), mod_ann.type, mod_ann.target, True]
                )

    for att_ann in ann_obj.get_attributes():
        # XXX: Hack to support Meta-knowledge
        if ':' in att_ann.type:
            _type, cue = att_ann.type.split(':')
        else:
            _type = att_ann.type
            cue = None

        j_dic['attributes'].append(
                [unicode(att_ann.id), _type, att_ann.target, att_ann.value, cue]
                )

    for com_ann in ann_obj.get_oneline_comments():
        j_dic['comments'].append(
                [com_ann.target, com_ann.type, com_ann.tail.strip()]
                )

    if ann_obj.failed_lines:
        error_msg = 'Unable to parse the following line(s):<br/>%s' % (
                '\n<br/>\n'.join(
                    [('%s: %s' % (
                        # The line number is off by one
                        unicode(line_num + 1),
                        unicode(ann_obj[line_num])
                        )).strip()
                    for line_num in ann_obj.failed_lines])
                    )
        display_message(error_msg, type='error', duration=len(ann_obj.failed_lines) * 3)

    j_dic['mtime'] = ann_obj.ann_mtime
    j_dic['ctime'] = ann_obj.ann_ctime

    try:
        if PERFORM_VERIFICATION:
            # XXX avoid digging the directory from the ann_obj
            import os
            docdir = os.path.dirname(ann_obj._document)
            projectconf = ProjectConfiguration(docdir)
            from verify_annotations import verify_annotation
            issues = verify_annotation(ann_obj, projectconf)
        else:
            issues = []
    except Exception, e:
        # TODO add an issue about the failure?
        issues = []
        display_message('Error: verify_annotation() failed: %s' % e, 'error', -1)

    for i in issues:
        j_dic['comments'].append((unicode(i.ann_id), i.type, i.description))

def _enrich_json_with_base(j_dic):
    # TODO: Make the names here and the ones in the Annotations object conform
    # This is the from offset
    j_dic['offset'] = 0
    j_dic['entities'] = []
    j_dic['events'] = []
    j_dic['relations'] = []
    j_dic['triggers'] = []
    j_dic['modifications'] = []
    j_dic['attributes'] = []
    j_dic['equivs'] = []
    j_dic['comments'] = []

def _document_json_dict(document):
    #TODO: DOC!

    j_dic = {}
    _enrich_json_with_base(j_dic)

    #TODO: We don't check if the files exist, let's be more error friendly
    # Read in the textual data to make it ready to push
    _enrich_json_with_text(j_dic, document + '.' + TEXT_FILE_SUFFIX)

    with TextAnnotations(document) as ann_obj:
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
            # NOTE: this also happens for missing write permissions, as
            # geniass assumes it can write a temporary into the directory
            # where the .txt is found.
            display_message("Warning: sentence split failed (geniass not set up, or no write permission to directory?)", type='warning')
            err = OSError()
            err.errno = 2
            raise err
        return ret
    except OSError, e:
        # If the file is not found we do an ugly fall-back, this is far
        # too general of an exception handling at the moment.
        if e.errno == 2:
            with open_textfile(txt_file_path, 'r') as txt_file:
                return sub(r'(\. *) ([A-Z])',r'\1\n\2', txt_file.read())
        else:
            raise

def get_document(directory, document):
    real_dir = real_directory(directory)
    doc_path = path_join(real_dir, document)
    return _document_json_dict(doc_path)
