#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

# XXX: This module along with stats and annotator is pretty much pure chaos



"""Document handling functionality.

Author:     Pontus Stenetorp    <pontus is s u-tokyo ac jp>
            Illes Solt          <solt tmit bme hu>
Version:    2011-04-21
"""

from errno import EACCES, ENOENT
from itertools import chain
from os import listdir
from os.path import join as path_join
from os.path import abspath, dirname, getmtime, isabs, isdir, normpath

from config import BASE_DIR, DATA_DIR

from annlog import annotation_logging_active
from annotation import (BIONLP_ST_2013_COMPATIBILITY, JOINED_ANN_FILE_SUFF,
                        TEXT_FILE_SUFFIX, AnnotationCollectionNotFoundError,
                        AnnotationFileNotFoundError, TextAnnotations,
                        open_textfile)
from auth import AccessDeniedError, allowed_to_read
from common import CollectionNotAccessibleError, ProtocolError
from message import Messager
from projectconfig import (ARC_DRAWING_ATTRIBUTES, ATTR_DRAWING_ATTRIBUTES,
                           SEPARATOR_STR, SPAN_DRAWING_ATTRIBUTES,
                           SPECIAL_RELATION_TYPES, VISUAL_ARC_DEFAULT,
                           VISUAL_ATTR_DEFAULT, VISUAL_SPAN_DEFAULT,
                           ProjectConfiguration,
                           get_annotation_config_section_labels,
                           options_get_ssplitter, options_get_tokenization,
                           options_get_validation,
                           visual_options_get_arc_bundle,
                           visual_options_get_text_direction)
from stats import get_statistics


def _fill_type_configuration(
        nodes,
        project_conf,
        hotkey_by_type,
        all_connections=None):
    # all_connections is an optimization to reduce invocations of
    # projectconfig methods such as arc_types_from_to.
    if all_connections is None:
        all_connections = project_conf.all_connections()

    items = []
    for node in nodes:
        if node == SEPARATOR_STR:
            items.append(None)
        else:
            item = {}
            _type = node.storage_form()

            # This isn't really a great place to put this, but we need
            # to block these magic values from getting to the client.
            # TODO: resolve cleanly, preferably by not storing this with
            # other relations at all.
            if _type in SPECIAL_RELATION_TYPES:
                continue

            item['name'] = project_conf.preferred_display_form(_type)
            item['type'] = _type
            item['unused'] = node.unused
            item['labels'] = project_conf.get_labels_by_type(_type)
            item['attributes'] = project_conf.attributes_for(_type)
            item['normalizations'] = node.normalizations()

            span_drawing_conf = project_conf.get_drawing_config_by_type(_type)
            if span_drawing_conf is None:
                span_drawing_conf = project_conf.get_drawing_config_by_type(
                    VISUAL_SPAN_DEFAULT)
            if span_drawing_conf is None:
                span_drawing_conf = {}
            for k in SPAN_DRAWING_ATTRIBUTES:
                if k in span_drawing_conf:
                    item[k] = span_drawing_conf[k]

            try:
                item['hotkey'] = hotkey_by_type[_type]
            except KeyError:
                pass

            arcs = []

            # Note: for client, relations are represented as "arcs"
            # attached to "spans" corresponding to entity annotations.

            # To avoid redundant entries, fill each type at most once.
            filled_arc_type = {}

            for arc in chain(
                    project_conf.relation_types_from(_type),
                    node.arg_list):
                if arc in filled_arc_type:
                    continue
                filled_arc_type[arc] = True

                curr_arc = {}
                curr_arc['type'] = arc

                arc_labels = project_conf.get_labels_by_type(arc)
                curr_arc['labels'] = arc_labels if arc_labels is not None else [arc]

                try:
                    curr_arc['hotkey'] = hotkey_by_type[arc]
                except KeyError:
                    pass

                arc_drawing_conf = project_conf.get_drawing_config_by_type(arc)
                if arc_drawing_conf is None:
                    arc_drawing_conf = project_conf.get_drawing_config_by_type(
                        VISUAL_ARC_DEFAULT)
                if arc_drawing_conf is None:
                    arc_drawing_conf = {}
                for k in ARC_DRAWING_ATTRIBUTES:
                    if k in arc_drawing_conf:
                        curr_arc[k] = arc_drawing_conf[k]

                # Client needs also possible arc 'targets',
                # defined as the set of types (entity or event) that
                # the arc can connect to

                # This bit doesn't make sense for relations, which are
                # already "arcs" (see comment above).
                # TODO: determine if this should be an error: relation
                # config should now go through _fill_relation_configuration
                # instead.
                if project_conf.is_relation_type(_type):
                    targets = []
                else:
                    targets = []

                    if arc in all_connections[_type]:
                        targets = all_connections[_type][arc]

                    # TODO: this code remains here to allow for further checking of the
                    # new all_connections() functionality. Comment out to activate
                    # verification of the new implementation (above) against the old one
                    # (below, commented out).
#                     check_targets = []
#                     for ttype in project_conf.get_entity_types() + project_conf.get_event_types():
#                         if arc in project_conf.arc_types_from_to(_type, ttype):
#                             check_targets.append(ttype)

#                     if targets == check_targets:
#                         Messager.info("CHECKS OUT!")
#                     elif sorted(targets) == sorted(check_targets):
#                         Messager.warning("Different sort order for %s -> %s:\n%s\n%s" % (_type, arc, str(targets), str(check_targets)), 10)
#                     else:
#                         Messager.error("Mismatch for %s -> %s:\n%s\n%s" % (_type, arc, str(sorted(targets)), str(sorted(check_targets))), -1)

                curr_arc['targets'] = targets

                arcs.append(curr_arc)

            # If we found any arcs, attach them
            if arcs:
                item['arcs'] = arcs

            item['children'] = _fill_type_configuration(
                node.children, project_conf, hotkey_by_type, all_connections)
            items.append(item)
    return items

# TODO: duplicates part of _fill_type_configuration


def _fill_relation_configuration(nodes, project_conf, hotkey_by_type):
    items = []
    for node in nodes:
        if node == SEPARATOR_STR:
            items.append(None)
        else:
            item = {}
            _type = node.storage_form()

            if _type in SPECIAL_RELATION_TYPES:
                continue

            item['name'] = project_conf.preferred_display_form(_type)
            item['type'] = _type
            item['unused'] = node.unused
            item['labels'] = project_conf.get_labels_by_type(_type)
            item['attributes'] = project_conf.attributes_for(_type)

            # TODO: avoid magic value
            item['properties'] = {}
            if '<REL-TYPE>' in node.special_arguments:
                for special_argument in node.special_arguments['<REL-TYPE>']:
                    item['properties'][special_argument] = True

            arc_drawing_conf = project_conf.get_drawing_config_by_type(_type)
            if arc_drawing_conf is None:
                arc_drawing_conf = project_conf.get_drawing_config_by_type(
                    VISUAL_ARC_DEFAULT)
            if arc_drawing_conf is None:
                arc_drawing_conf = {}
            for k in ARC_DRAWING_ATTRIBUTES:
                if k in arc_drawing_conf:
                    item[k] = arc_drawing_conf[k]

            try:
                item['hotkey'] = hotkey_by_type[_type]
            except KeyError:
                pass

            # minimal info on argument types to allow differentiation of e.g.
            # "Equiv(Protein, Protein)" and "Equiv(Organism, Organism)"
            args = []
            for arg in node.arg_list:
                curr_arg = {}
                curr_arg['role'] = arg
                # TODO: special type (e.g. "<ENTITY>") expansion via
                # projectconf
                curr_arg['targets'] = node.arguments[arg]

                args.append(curr_arg)

            item['args'] = args

            item['children'] = _fill_relation_configuration(
                node.children, project_conf, hotkey_by_type)
            items.append(item)
    return items


# TODO: this may not be a good spot for this
def _fill_attribute_configuration(nodes, project_conf):
    items = []
    for node in nodes:
        if node == SEPARATOR_STR:
            continue
        else:
            item = {}
            _type = node.storage_form()
            item['name'] = project_conf.preferred_display_form(_type)
            item['type'] = _type
            item['unused'] = node.unused
            item['labels'] = project_conf.get_labels_by_type(_type)

            attr_drawing_conf = project_conf.get_drawing_config_by_type(_type)
            if attr_drawing_conf is None:
                attr_drawing_conf = project_conf.get_drawing_config_by_type(
                    VISUAL_ATTR_DEFAULT)
            if attr_drawing_conf is None:
                attr_drawing_conf = {}

            # Check if the possible values for the argument are specified
            # TODO: avoid magic strings
            if "Value" in node.arguments:
                args = node.arguments["Value"]
            else:
                # no "Value" defined; assume binary.
                args = []

            # Check if a default value is specified for the attribute
            if '<DEFAULT>' in node.special_arguments:
                try:
                    item['default'] = node.special_arguments['<DEFAULT>'][0]
                except IndexError:
                    Messager.warning(
                        "Config error: empty <DEFAULT> for %s" %
                        item['name'])

            # Each item's 'values' entry is a list of dictionaries, one
            # dictionary per value option.
            if len(args) == 0:
                # binary; use drawing config directly
                attr_values = {'name': _type}
                for k in ATTR_DRAWING_ATTRIBUTES:
                    if k in attr_drawing_conf:
                        # protect against error from binary attribute
                        # having multi-valued visual config (#698)
                        if isinstance(attr_drawing_conf[k], list):
                            Messager.warning(
                                "Visual config error: expected single value for %s binary attribute '%s' config, found %d. Visuals may be wrong." %
                                (_type, k, len(
                                    attr_drawing_conf[k])))
                            # fall back on the first just to have something.
                            attr_values[k] = attr_drawing_conf[k][0]
                        else:
                            attr_values[k] = attr_drawing_conf[k]
                item['values'] = [attr_values]
            else:
                # has normal arguments, use these as possible values.
                # (this is quite terrible all around, sorry.)
                # we'll populate this incrementally as we process the args
                item['values'] = []
                for i, v in enumerate(args):
                    attr_values = {'name': v}

                    # match up annotation config with drawing config by
                    # position in list of alternative values so that e.g.
                    # "Values:L1|L2|L3" can have the visual config
                    # "glyph:[1]|[2]|[3]". If only a single value is
                    # defined, apply to all.
                    for k in ATTR_DRAWING_ATTRIBUTES:
                        if k in attr_drawing_conf:
                            # (sorry about this)
                            if isinstance(attr_drawing_conf[k], list):
                                # sufficiently many specified?
                                if len(attr_drawing_conf[k]) > i:
                                    attr_values[k] = attr_drawing_conf[k][i]
                                else:
                                    Messager.warning(
                                        "Visual config error: expected %d values for %s attribute '%s' config, found only %d. Visuals may be wrong." %
                                        (len(args), v, k, len(
                                            attr_drawing_conf[k])))
                            else:
                                # single value (presumably), apply to all
                                attr_values[k] = attr_drawing_conf[k]

                    # if no drawing attribute was defined, fall back to
                    # using a glyph derived from the attribute value
                    if len([k for k in ATTR_DRAWING_ATTRIBUTES if
                            k in attr_values]) == 0:
                        attr_values['glyph'] = '[' + v + ']'

                    item['values'].append(attr_values)

            items.append(item)
    return items


def _fill_visual_configuration(types, project_conf):
    # similar to _fill_type_configuration, but for types for which
    # full annotation configuration was not found but some visual
    # configuration can be filled.

    # TODO: duplicates parts of _fill_type_configuration; combine?
    items = []
    for _type in types:
        item = {}
        item['name'] = project_conf.preferred_display_form(_type)
        item['type'] = _type
        item['unused'] = True
        item['labels'] = project_conf.get_labels_by_type(_type)

        drawing_conf = project_conf.get_drawing_config_by_type(_type)
        # not sure if this is a good default, but let's try
        if drawing_conf is None:
            drawing_conf = project_conf.get_drawing_config_by_type(
                VISUAL_SPAN_DEFAULT)
        if drawing_conf is None:
            drawing_conf = {}
        # just plug in everything found, whether for a span or arc
        for k in chain(SPAN_DRAWING_ATTRIBUTES, ARC_DRAWING_ATTRIBUTES):
            if k in drawing_conf:
                item[k] = drawing_conf[k]

        # TODO: anything else?

        items.append(item)

    return items

# TODO: this is not a good spot for this


def get_base_types(directory):
    project_conf = ProjectConfiguration(directory)

    keymap = project_conf.get_kb_shortcuts()
    hotkey_by_type = dict((v, k) for k, v in keymap.items())

    # fill config for nodes for which annotation is configured

    # calculate once only (this can get heavy)
    all_connections = project_conf.all_connections()

    event_hierarchy = project_conf.get_event_type_hierarchy()
    event_types = _fill_type_configuration(
        event_hierarchy,
        project_conf,
        hotkey_by_type,
        all_connections)

    entity_hierarchy = project_conf.get_entity_type_hierarchy()
    entity_types = _fill_type_configuration(
        entity_hierarchy,
        project_conf,
        hotkey_by_type,
        all_connections)

    relation_hierarchy = project_conf.get_relation_type_hierarchy()
    relation_types = _fill_relation_configuration(relation_hierarchy,
                                                  project_conf, hotkey_by_type)

    # make visual config available also for nodes for which there is
    # no annotation config. Note that defaults (SPAN_DEFAULT etc.)
    # are included via get_drawing_types() if defined.
    unconfigured = [l for l in (list(project_conf.get_labels().keys()) +
                                project_conf.get_drawing_types()) if
                    not project_conf.is_configured_type(l)]
    unconf_types = _fill_visual_configuration(unconfigured, project_conf)

    return event_types, entity_types, relation_types, unconf_types


def get_attribute_types(directory):
    project_conf = ProjectConfiguration(directory)

    entity_attribute_hierarchy = project_conf.get_entity_attribute_type_hierarchy()
    entity_attribute_types = _fill_attribute_configuration(
        entity_attribute_hierarchy, project_conf)

    relation_attribute_hierarchy = project_conf.get_relation_attribute_type_hierarchy()
    relation_attribute_types = _fill_attribute_configuration(
        relation_attribute_hierarchy, project_conf)

    event_attribute_hierarchy = project_conf.get_event_attribute_type_hierarchy()
    event_attribute_types = _fill_attribute_configuration(
        event_attribute_hierarchy, project_conf)

    return entity_attribute_types, relation_attribute_types, event_attribute_types


def get_search_config(directory):
    return ProjectConfiguration(directory).get_search_config()


def get_disambiguator_config(directory):
    return ProjectConfiguration(directory).get_disambiguator_config()


def get_normalization_config(directory):
    return ProjectConfiguration(directory).get_normalization_config()


def get_annotator_config(directory):
    # TODO: "annotator" is a very confusing term for a web service
    # that does automatic annotation in the context of a tool
    # where most annotators are expected to be human. Rethink.
    return ProjectConfiguration(directory).get_annotator_config()


def assert_allowed_to_read(doc_path):
    if not allowed_to_read(doc_path):
        raise AccessDeniedError  # Permission denied by access control


def real_directory(directory, rel_to=DATA_DIR):
    assert isabs(directory), 'directory "%s" is not absolute' % directory
    return path_join(rel_to, directory[1:])


def relative_directory(directory):
    # inverse of real_directory
    assert isabs(directory), 'directory "%s" is not absolute' % directory
    assert directory.startswith(DATA_DIR), 'directory "%s" not under DATA_DIR'
    return directory[len(DATA_DIR):]


def _is_hidden(file_name):
    return file_name.startswith('hidden_') or file_name.startswith('.')


def _listdir(directory):
    # return listdir(directory)
    try:
        assert_allowed_to_read(directory)
        return [f for f in listdir(directory) if not _is_hidden(f)
                and allowed_to_read(path_join(directory, f))]
    except OSError as e:
        Messager.error("Error listing %s: %s" % (directory, e))
        raise AnnotationCollectionNotFoundError(directory)


def _getmtime(file_path):
    """Internal wrapper of getmtime that handles access denied and invalid
    paths according to our specification.

    Arguments:

    file_path - path to the file to get the modification time for
    """

    try:
        return getmtime(file_path)
    except OSError as e:
        if e.errno in (EACCES, ENOENT):
            # The file did not exist or permission denied, we use -1 to
            #   indicate this since mtime > 0 is an actual time.
            return -1
        else:
            # We are unable to handle this exception, pass it one
            raise


class InvalidConfiguration(ProtocolError):
    def json(self, json_dic):
        json_dic['exception'] = 'invalidConfiguration'
        return json_dic


# TODO: Is this what we would call the configuration? It is minimal.
def get_configuration(name):
    # TODO: Rip out this path somewhere
    config_dir = path_join(BASE_DIR, 'configurations')
    for conf_name in listdir(config_dir):
        if conf_name == name:
            config_path = path_join(config_dir, conf_name)
            break
    else:
        raise InvalidConfiguration

    return _inject_annotation_type_conf(config_path)


def _inject_annotation_type_conf(dir_path, json_dic=None):
    if json_dic is None:
        json_dic = {}

    (event_types, entity_types, rel_types,
     unconf_types) = get_base_types(dir_path)
    (entity_attr_types, rel_attr_types,
     event_attr_types) = get_attribute_types(dir_path)

    json_dic['event_types'] = event_types
    json_dic['entity_types'] = entity_types
    json_dic['relation_types'] = rel_types
    json_dic['event_attribute_types'] = event_attr_types
    json_dic['relation_attribute_types'] = rel_attr_types
    json_dic['entity_attribute_types'] = entity_attr_types
    json_dic['unconfigured_types'] = unconf_types

    # inject annotation category aliases (e.g. "entities" -> "spans")
    # used in config (#903).
    section_labels = get_annotation_config_section_labels(dir_path)
    json_dic['ui_names'] = {}
    for c in ['entities', 'relations', 'events', 'attributes']:
        json_dic['ui_names'][c] = section_labels.get(c, c)

    # inject general visual options (currently just arc bundling) (#949)
    visual_options = {}
    visual_options['arc_bundle'] = visual_options_get_arc_bundle(dir_path)
    visual_options['text_direction'] = visual_options_get_text_direction(
        dir_path)
    json_dic['visual_options'] = visual_options

    return json_dic

# TODO: This is not the prettiest of functions


def get_directory_information(collection):
    directory = collection

    real_dir = real_directory(directory)

    assert_allowed_to_read(real_dir)

    # Get the document names
    base_names = [fn[0:-4] for fn in _listdir(real_dir)
                  if fn.endswith('txt')]

    doclist = base_names[:]
    doclist_header = [("Document", "string")]

    # Then get the modification times
    doclist_with_time = []
    for file_name in doclist:
        file_path = path_join(DATA_DIR, real_dir,
                              file_name + "." + JOINED_ANN_FILE_SUFF)
        doclist_with_time.append([file_name, _getmtime(file_path)])
    doclist = doclist_with_time
    doclist_header.append(("Modified", "time"))

    try:
        stats_types, doc_stats = get_statistics(real_dir, base_names)
    except OSError:
        # something like missing access permissions?
        raise CollectionNotAccessibleError

    doclist = [doclist[i] + doc_stats[i] for i in range(len(doclist))]
    doclist_header += stats_types

    dirlist = [dir for dir in _listdir(real_dir)
               if isdir(path_join(real_dir, dir))]
    # just in case, and for generality
    dirlist = [[dir] for dir in dirlist]

    # check whether at root, ignoring e.g. possible trailing slashes
    if normpath(real_dir) != normpath(DATA_DIR):
        parent = abspath(path_join(real_dir, '..'))[len(DATA_DIR) + 1:]
        # to get consistent processing client-side, add explicitly to list
        dirlist.append([".."])
    else:
        parent = None

    # combine document and directory lists, adding a column
    # differentiating files from directories and an unused column (can
    # point to a specific annotation) required by the protocol.  The
    # values filled here for the first are "c" for "collection"
    # (i.e. directory) and "d" for "document".
    combolist = []
    for i in dirlist:
        combolist.append(["c", None] + i)
    for i in doclist:
        combolist.append(["d", None] + i)

    # plug in the search config too
    search_config = get_search_config(real_dir)

    # ... and the disambiguator config ... this is getting a bit much
    disambiguator_config = get_disambiguator_config(real_dir)

    # ... and the normalization config (TODO: rethink)
    normalization_config = get_normalization_config(real_dir)

    # read in README (if any) to send as a description of the
    # collection
    try:
        with open_textfile(path_join(real_dir, "README")) as txt_file:
            readme_text = txt_file.read()
    except IOError:
        readme_text = None

    # fill in a flag for whether annotator logging is active so that
    # the client knows whether to invoke timing actions
    ann_logging = annotation_logging_active(real_dir)

    # fill in NER services, if any
    ner_taggers = get_annotator_config(real_dir)

    return _inject_annotation_type_conf(real_dir, json_dic={
        'items': combolist,
        'header': doclist_header,
        'parent': parent,
        'messages': [],
        'description': readme_text,
        'search_config': search_config,
        'disambiguator_config': disambiguator_config,
        'normalization_config': normalization_config,
        'annotation_logging': ann_logging,
        'ner_taggers': ner_taggers,
    })


class UnableToReadTextFile(ProtocolError):
    def __init__(self, path):
        self.path = path

    def __str__(self):
        return 'Unable to read text file %s' % self.path

    def json(self, json_dic):
        json_dic['exception'] = 'unableToReadTextFile'
        return json_dic


class IsDirectoryError(ProtocolError):
    def __init__(self, path):
        self.path = path

    def __str__(self):
        return ''

    def json(self, json_dic):
        json_dic['exception'] = 'isDirectoryError'
        return json_dic

# TODO: All this enrichment isn't a good idea, at some point we need an object


def _enrich_json_with_text(j_dic, txt_file_path, raw_text=None):
    if raw_text is not None:
        # looks like somebody read this already; nice
        text = raw_text
    else:
        # need to read raw text
        try:
            with open_textfile(txt_file_path, 'r') as txt_file:
                text = txt_file.read()
        except IOError:
            raise UnableToReadTextFile(txt_file_path)
        except UnicodeDecodeError:
            Messager.error(
                'Error reading text file: nonstandard encoding or binary?', -1)
            raise UnableToReadTextFile(txt_file_path)

    j_dic['text'] = text


    tokeniser = options_get_tokenization(dirname(txt_file_path))

    # First, generate tokenisation
    if tokeniser == 'mecab':
        from tokenise import jp_token_boundary_gen
        tok_offset_gen = jp_token_boundary_gen
    elif tokeniser == 'whitespace':
        from tokenise import whitespace_token_boundary_gen
        tok_offset_gen = whitespace_token_boundary_gen
    elif tokeniser == 'ptblike':
        from tokenise import gtb_token_boundary_gen
        tok_offset_gen = gtb_token_boundary_gen
    else:
        Messager.warning('Unrecognized tokenisation option '
                         ', reverting to whitespace tokenisation.')
        from tokenise import whitespace_token_boundary_gen
        tok_offset_gen = whitespace_token_boundary_gen
    j_dic['token_offsets'] = [o for o in tok_offset_gen(text)]

    ssplitter = options_get_ssplitter(dirname(txt_file_path))
    if ssplitter == 'newline':
        from ssplit import newline_sentence_boundary_gen
        ss_offset_gen = newline_sentence_boundary_gen
    elif ssplitter == 'regex':
        from ssplit import regex_sentence_boundary_gen
        ss_offset_gen = regex_sentence_boundary_gen
    else:
        Messager.warning('Unrecognized sentence splitting option '
                         ', reverting to newline sentence splitting.')
        from ssplit import newline_sentence_boundary_gen
        ss_offset_gen = newline_sentence_boundary_gen
    j_dic['sentence_offsets'] = [o for o in ss_offset_gen(text)]

    return True


def _enrich_json_with_data(j_dic, ann_obj):
    # TODO: figure out if there's a reason for all the str()
    # invocations here; remove if not.

    # We collect trigger ids to be able to link the textbound later on
    trigger_ids = set()
    for event_ann in ann_obj.get_events():
        trigger_ids.add(event_ann.trigger)
        j_dic['events'].append(
            [str(event_ann.id), str(event_ann.trigger), event_ann.args]
        )

    for rel_ann in ann_obj.get_relations():
        j_dic['relations'].append(
            [str(rel_ann.id), str(rel_ann.type),
             [(rel_ann.arg1l, rel_ann.arg1),
              (rel_ann.arg2l, rel_ann.arg2)]]
        )

    for tb_ann in ann_obj.get_textbounds():
        #j_tb = [str(tb_ann.id), tb_ann.type, tb_ann.start, tb_ann.end]
        j_tb = [str(tb_ann.id), tb_ann.type, tb_ann.spans]

        # If we spotted it in the previous pass as a trigger for an
        # event or if the type is known to be an event type, we add it
        # as a json trigger.
        # TODO: proper handling of disconnected triggers. Currently
        # these will be erroneously passed as 'entities'
        if str(tb_ann.id) in trigger_ids:
            j_dic['triggers'].append(j_tb)
            # special case for BioNLP ST 2013 format: send triggers
            # also as entities for those triggers that are referenced
            # from annotations other than events (#926).
            if BIONLP_ST_2013_COMPATIBILITY:
                if tb_ann.id in ann_obj.externally_referenced_triggers:
                    try:
                        j_dic['entities'].append(j_tb)
                    except KeyError:
                        j_dic['entities'] = [j_tb, ]
        else:
            try:
                j_dic['entities'].append(j_tb)
            except KeyError:
                j_dic['entities'] = [j_tb, ]

    for eq_ann in ann_obj.get_equivs():
        j_dic['equivs'].append(
            (['*', eq_ann.type]
             + [e for e in eq_ann.entities])
        )

    for att_ann in ann_obj.get_attributes():
        j_dic['attributes'].append([str(att_ann.id), str(
            att_ann.type), str(att_ann.target), att_ann.value])

    for norm_ann in ann_obj.get_normalizations():
        j_dic['normalizations'].append(
            [str(norm_ann.id), str(norm_ann.type),
             str(norm_ann.target), str(norm_ann.refdb),
             str(norm_ann.refid), str(norm_ann.reftext)]
        )

    for com_ann in ann_obj.get_oneline_comments():
        comment = [com_ann.target, str(com_ann.type),
                   com_ann.tail.strip()]
        try:
            j_dic['comments'].append(comment)
        except KeyError:
            j_dic['comments'] = [comment, ]

    if ann_obj.failed_lines:
        error_msg = 'Unable to parse the following line(s):\n%s' % (
            '\n'.join(
                    [('%s: %s' % (
                        # The line number is off by one
                        str(line_num + 1),
                        str(ann_obj[line_num])
                    )).strip()
                        for line_num in ann_obj.failed_lines])
        )
        Messager.error(error_msg, duration=len(ann_obj.failed_lines) * 3)

    j_dic['mtime'] = ann_obj.ann_mtime
    j_dic['ctime'] = ann_obj.ann_ctime

    try:
        # XXX avoid digging the directory from the ann_obj
        import os
        docdir = os.path.dirname(ann_obj._document)
        if options_get_validation(docdir) in ('all', 'full', ):
            from verify_annotations import verify_annotation
            projectconf = ProjectConfiguration(docdir)
            issues = verify_annotation(ann_obj, projectconf)
        else:
            issues = []
    except Exception as e:
        # TODO add an issue about the failure?
        issues = []
        Messager.error('Error: verify_annotation() failed: %s' % e, -1)

    for i in issues:
        issue = (str(i.ann_id), i.type, i.description)
        try:
            j_dic['comments'].append(issue)
        except BaseException:
            j_dic['comments'] = [issue, ]

    # Attach the source files for the annotations and text
    from os.path import splitext
    from annotation import TEXT_FILE_SUFFIX
    ann_files = [splitext(p)[1][1:] for p in ann_obj._input_files]
    ann_files.append(TEXT_FILE_SUFFIX)
    ann_files = sorted([p for p in set(ann_files)])
    j_dic['source_files'] = ann_files


def _enrich_json_with_base(j_dic):
    # TODO: Make the names here and the ones in the Annotations object conform

    # TODO: "from offset" of what? Commented this out, remove once
    # sure that nothing is actually using this.
    #     # This is the from offset
    #     j_dic['offset'] = 0

    for d in (
        'entities',
        'events',
        'relations',
        'triggers',
        'modifications',
        'attributes',
        'equivs',
        'normalizations',
        'comments',
    ):
        j_dic[d] = []


def _document_json_dict(document):
    # TODO: DOC!

    # pointing at directory instead of document?
    if isdir(document):
        raise IsDirectoryError(document)

    j_dic = {}
    _enrich_json_with_base(j_dic)

    # TODO: We don't check if the files exist, let's be more error friendly
    # Read in the textual data to make it ready to push
    _enrich_json_with_text(j_dic, document + '.' + TEXT_FILE_SUFFIX)

    with TextAnnotations(document) as ann_obj:
        # Note: At this stage the sentence offsets can conflict with the
        #   annotations, we thus merge any sentence offsets that lie within
        #   annotations
        # XXX: ~O(tb_ann * sentence_breaks), can be optimised
        # XXX: The merge strategy can lead to unforeseen consequences if two
        #   sentences are not adjacent (the format allows for this:
        #   S_1: [0, 10], S_2: [15, 20])
        s_breaks = j_dic['sentence_offsets']
        for tb_ann in ann_obj.get_textbounds():
            s_i = 0
            while s_i < len(s_breaks):
                s_start, s_end = s_breaks[s_i]
                # Does any subspan of the annotation strech over the
                # end of the sentence?
                found_spanning = False
                for tb_start, tb_end in tb_ann.spans:
                    if tb_start < s_end and tb_end > s_end:
                        found_spanning = True
                        break
                if found_spanning:
                    # Merge this sentence and the next sentence
                    s_breaks[s_i] = (s_start, s_breaks[s_i + 1][1])
                    del s_breaks[s_i + 1]
                else:
                    s_i += 1

        _enrich_json_with_data(j_dic, ann_obj)

    return j_dic


def get_document(collection, document):
    directory = collection
    real_dir = real_directory(directory)
    doc_path = path_join(real_dir, document)
    return _document_json_dict(doc_path)


def get_document_timestamp(collection, document):
    directory = collection
    real_dir = real_directory(directory)
    assert_allowed_to_read(real_dir)
    doc_path = path_join(real_dir, document)
    ann_path = doc_path + '.' + JOINED_ANN_FILE_SUFF
    mtime = _getmtime(ann_path)

    return {
        'mtime': mtime,
    }
