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
from message import Messager

try:
    from config import PERFORM_VERIFICATION
except ImportError:
    PERFORM_VERIFICATION = False

try:
    from config import JAPANESE
except ImportError:
    JAPANESE = False

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
            # TODO: use project_conf
            item['labels'] = get_labels_by_storage_form(directory, _type)

            # TODO: avoid magic values
            span_drawing_conf = project_conf.get_drawing_config_by_type(_type) 
            if span_drawing_conf is None:
                span_drawing_conf = project_conf.get_drawing_config_by_type("SPAN_DEFAULT")
            if span_drawing_conf is None:
                span_drawing_conf = {}
            for k in ('fgColor', 'bgColor', 'borderColor'):
                if k in span_drawing_conf:
                    item[k] = span_drawing_conf[k]
            
            try:
                item['hotkey'] = hotkey_by_type[_type]
            except KeyError:
                pass

            arcs = []
            # Note: for client, relations are represented as "arcs"
            # attached to "spans" corresponding to entity annotations.
            for arc in chain(project_conf.relation_types_from(_type), node.arguments.keys()):
                curr_arc = {}
                curr_arc['type'] = arc

                arc_labels = get_labels_by_storage_form(directory, arc)
                if arc_labels is not None:
                    curr_arc['labels'] = arc_labels if arc_labels is not None else [arc]

                try:
                    curr_arc['hotkey'] = hotkey_by_type[arc]
                except KeyError:
                    pass
                
                # TODO: avoid magic values
                arc_drawing_conf = project_conf.get_drawing_config_by_type(arc)
                if arc_drawing_conf is None:
                    arc_drawing_conf = project_conf.get_drawing_config_by_type("ARC_DEFAULT")
                if arc_drawing_conf is None:
                    arc_drawing_conf = {}
                for k in ('color', 'dashArray'):
                    if k in arc_drawing_conf:
                        curr_arc[k] = arc_drawing_conf[k]                    

                # Client needs also possible arc 'targets',
                # defined as the set of types (entity or event) that
                # the arc can connect to
                targets = []
                # TODO: should include this functionality in projectconf
                for ttype in project_conf.get_entity_types() + project_conf.get_event_types():
                    if arc in project_conf.arc_types_from_to(_type, ttype):
                        targets.append(ttype)
                curr_arc['targets'] = targets

                arcs.append(curr_arc)
                    
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

            # process "special" <GLYPH-POS> argument, specifying where
            # to place the glyph
            glyph_pos = None
            for k in node.arguments:
                # TODO: remove magic value
                if k == '<GLYPH-POS>':
                    for v in node.arguments[k]:
                        if v not in ('left', 'right'):
                            display_message('Configuration error: "%s" is not a valid glyph position for %s' % (v,_type), 'warning')
                        else:
                            glyph_pos = v

            # TODO: "special" <DEFAULT> argument
            
            # check if there are any (normal) "arguments"
            args = [k for k in node.arguments if k != "Arg" and not match(r'^<.*>$', k)]
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
                for k in args:
                    for v in node.arguments[k]:
                        item['values'][k] = { 'glyph':v }
                        if glyph_pos is not None:
                            item['values'][k]['position'] = glyph_pos

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

def relative_directory(directory):
    # inverse of real_directory
    assert isabs(directory), 'directory "%s" is not absolute' % directory
    assert directory.startswith(DATA_DIR), 'directory "%s" not under DATA_DIR'
    return directory[len(DATA_DIR):]

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

    stats_types, doc_stats = get_statistics(real_dir, base_names)
                
    doclist = [doclist[i] + doc_stats[i] for i in range(len(doclist))]
    doclist_header += stats_types

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
        with open_textfile(txt_file_path) as txt_file:
            text = txt_file.read()
    except IOError:
        raise UnableToReadTextFile(txt_file_path)
    except UnicodeDecodeError:
        Messager.error('Error reading text file: nonstandard encoding or binary?', -1)
        raise UnableToReadTextFile(txt_file_path)

    # TODO XXX huge hack, sorry, the client currently crashing on
    # chrome for two or more consecutive space, so replace every
    # second with literal non-breaking space. Note that this is just
    # for the client display -- server-side storage is not affected.
    text = text.replace("  ", ' '+unichr(0x00A0))

    j_dic['text'] = text
    
    from logging import info as log_info

    if JAPANESE:
        from ssplit import jp_sentence_boundary_gen
        from tokenise import jp_token_boundary_gen

        sentence_offsets = [o for o in jp_sentence_boundary_gen(text)]
        #log_info('offsets: ' + str(offsets))
        j_dic['sentence_offsets'] = sentence_offsets

        token_offsets = [o for o in jp_token_boundary_gen(text)]
        j_dic['token_offsets'] = token_offsets
    else:
        from ssplit import en_sentence_boundary_gen
        from tokenise import en_token_boundary_gen

        sentence_offsets = [o for o in en_sentence_boundary_gen(text)]
        #log_info('offsets: ' + str(sentence_offsets))
        j_dic['sentence_offsets'] = sentence_offsets
        
        token_offsets = [o for o in en_token_boundary_gen(text)]
        j_dic['token_offsets'] = token_offsets

    return True

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

    for att_ann in ann_obj.get_attributes():
        j_dic['attributes'].append(
                [unicode(att_ann.id), att_ann.type, att_ann.target, att_ann.value]
                )

    for com_ann in ann_obj.get_oneline_comments():
        j_dic['comments'].append(
                [com_ann.target, com_ann.type, com_ann.tail.strip()]
                )

    if ann_obj.failed_lines:
        error_msg = 'Unable to parse the following line(s):\n%s' % (
                '\n'.join(
                [('%s: %s' % (
                            # The line number is off by one
                            unicode(line_num + 1),
                            unicode(ann_obj[line_num])
                            )).strip()
                 for line_num in ann_obj.failed_lines])
                )
        Messager.error(error_msg, duration=len(ann_obj.failed_lines) * 3)

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
        Messager.error('Error: verify_annotation() failed: %s' % e, -1)

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

def get_document(directory, document):
    real_dir = real_directory(directory)
    doc_path = path_join(real_dir, document)
    return _document_json_dict(doc_path)
