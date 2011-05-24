#!/usr/bin/env python
# coding=utf-8
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 fileencoding=utf-8 autoindent:

from __future__ import with_statement

'''
Server-side HTML generation-related functionality for
Brat Rapid Annotation Tool (brat)
'''

# TODO: This module is largely deprecated and is to be deleted.

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

from projectconfig import (ProjectConfiguration, get_labels_by_storage_form,
        get_attribute_type_hierarchy)

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
  
    # XXX: Temporary hack until the configurations support values
    attribute_types = [
            {
                'name': 'Negation',
                'type': 'Negation',
                'values': {
                    'Negation': {
                        'box': u'crossed',
                        },
                    },
                'labels': ['Negation', ],
                'unused': False,
                },
            {
                'name': 'Speculation',
                'type': 'Speculation',
                'values': {
                    'Speculation': {
                        'dasharray': '3,3',
                        },
                    },
                'labels': ['Speculation', ],
                'unused': False,
                },
            # Hard-coded Meta-Knowledge types
            # Characters picked by: http://unicode.bloople.net/
            # TODO: Assign sensible characters
            {
                'name': 'Knowledge Type',
                'type': 'KT',
                'labels': ['Knowledge Type', ],
                'values': {
                    'Investigation': {
                        'glyph': u'Ⓘ',
                        },
                    'Analysis': {
                        'glyph': u'Ⓐ',
                        },
                    'Observation': {
                        'glyph': u'Ⓞ',
                        },
                    'Gen-Fact': {
                        'glyph': u'Ⓕ',
                        },
                    'Gen-Method': {
                        'glyph': u'Ⓜ',
                        },
                    'Gen-Other': {
                        'glyph': u'Ⓣ',
                        },
                    },
                'unused': True,
                },
            {
                'name': 'Certainty Level',
                'type': 'CL',
                'labels': ['Certainty Level', ],
                'values': {
                    'L1': {
                        'glyph': u'➊',
                        'position': 'left',
                        },
                    'L2': {
                        'glyph': u'➋',
                        'position': 'left',
                        },
                    'L3': {
                        'glyph': u'➌',
                        'position': 'left',
                        },
                    },
                'unused': True,
                },
            {
                'name': 'Polarity',
                'type': 'Polarity',
                'labels': ['Polarity', ],
                'values': {
                    'Negative': {
                        'glyph': u'✕',
                        'position': 'left',
                        },
                    'Positive': {
                        'glyph': u'✓',
                        'position': 'left',
                        },
                    },
                'unused': True,
                },
            {
                'name': 'Manner',
                'type': 'Manner',
                'labels': ['Manner', ],
                'values': {
                    'High': {
                        'glyph': u'↑',
                        },
                    'Low': {
                        'glyph': u'↓',
                        },
                    'Neutral': {
                        'glyph': u'↔',
                        },
                    },
                'unused': True,
                },
            {
                'name': 'Source',
                'type': 'Source',
                'labels': ['Source', ],
                'values': {
                    'Other': {
                        'glyph': u'⇗',
                        },
                    'Current': {
                        'glyph': u'⇙',
                        },
                    },
                'unused': True,
                },
            ]

    from projectconfig import get_relation_type_hierarchy
    relation_hierarchy = get_relation_type_hierarchy(directory)
    relation_types = _get_subtypes_for_type(relation_hierarchy,
            project_conf, hotkey_by_type, directory)

    return event_types, entity_types, attribute_types, relation_types

def escape(s):
    from cgi import escape as cgi_escape
    return cgi_escape(s).replace('"', '&quot;');

def __generate_input_and_label(t, dt, keymap, indent, disabled, prefix):
    l = []
    # TODO: remove check once debugged; the storage form t should not
    # require any sort of escaping
    assert " " not in t, "INTERNAL ERROR: space in storage form"
    if not disabled:
        dstr = ""
    else:
        dstr = ' disabled="disabled"'
    s  = indent+'    <input id="%s%s" type="radio" name="%stype" value="%s" %s/>' % (prefix, t, prefix, t, dstr)
    s += '<label for="%s%s">' % (prefix, t)

    if t in keymap:
        # -1 if not found (i.e. key unrelated to string)
        key_offset= dt.lower().find(keymap[t].lower())
    else:
        key_offset = -1

    if key_offset == -1:
        s += '%s</label>' % escape(dt)
    else:        
        s += '%s<span class="accesskey">%s</span>%s</label>' % (escape(dt[:key_offset]), escape(dt[key_offset:key_offset+1]), escape(dt[key_offset+1:]))
    l.append(s)
    return l

def __generate_span_input_and_label(t, dt, keymap, indent, disabled):
    return __generate_input_and_label(t, dt, keymap, indent, disabled, "span_")

def __generate_arc_input_and_label(t, dt, keymap):
    return __generate_input_and_label(t, dt, keymap, "", False, "arc_")

def __generate_node_html_lines(node, keymap, projectconf, depth=0):
    # TODO: make this less exceptional, avoid magic values
    if node == "SEPARATOR":
        return ["<hr/>"]

    t  = node.storage_form()
    dt = projectconf.preferred_display_form(t)

    # for debugging
    indent = " "*6*depth
    lines = []
    if len(node.children) == 0:
        # simple item
        lines.append(indent+'<div class="item">')
        lines.append(indent+'  <div class="item_content">')
        lines += __generate_span_input_and_label(t, dt, keymap, indent, node.unused)
        lines.append(indent+'  </div>')
        lines.append(indent+'</div>')
    else:
        # collapsible item with children
        lines.append(indent+'<div class="item">')
        lines.append(indent+'  <div class="collapser open"></div>')
        lines.append(indent+'  <div class="item_content">')
        lines += __generate_span_input_and_label(t, dt, keymap, indent, node.unused)
        lines.append(indent+'    <div class="collapsible open">')

        for n in node.children:
             lines += __generate_node_html_lines(n, keymap, projectconf, depth+1)

        lines.append(indent+'    </div>')
        lines.append(indent+'  </div>')
        lines.append(indent+'</div>')

    return lines

def __generate_term_hierarchy_html(root_nodes, type_key_map, projectconf):
    all_lines = []
    for n in root_nodes:
        all_lines += __generate_node_html_lines(n, type_key_map, projectconf)
    return "\n".join(all_lines)

def generate_entity_type_html(projectconf, type_key_map):
    hierarchy = projectconf.get_entity_type_hierarchy()
    return __generate_term_hierarchy_html(hierarchy, type_key_map, projectconf)
                                          
def generate_event_type_html(projectconf, type_key_map):
    hierarchy = projectconf.get_event_type_hierarchy()
    return __generate_term_hierarchy_html(hierarchy, type_key_map, projectconf)

def generate_event_attribute_html(projectconf, type_key_map):
    # TODO: proper checks of which attributes go with events;
    # currently assuming all are OK.
    lines = []
    for t in projectconf.get_attribute_types():
        lines.append("""<input id="span_mod_%s" type="checkbox" value="%s"/>""" % (t,t))
        # TODO: mark accesskey as in __generate_input_and_label
        lines.append("""<label for="span_mod_%s">%s</label>""" % (t,t))
    return "\n".join(lines)

def generate_client_keymap(keyboard_shortcuts):
    client_keymap = {}
    for k in keyboard_shortcuts:
        client_keymap[k] = 'span_'+keyboard_shortcuts[k]
    return client_keymap

def select_keyboard_shortcuts(strings):
    """
    Given a set of strings, greedily selects a shortcut key for each from
    letters not previously selected. Returns a dictionary keyed by
    upper-cased shortcut letters to the strings. Note that some strings
    map not be in the dictionary if all their letters were previously
    taken.
    """
    shortcuts = {}
    key_taken = {}

    for s in strings:
        for i in range(len(s)):
            if s[i].lower() not in key_taken:
                key_taken[s[i].lower()] = True
                shortcuts[s[i].upper()] = s
                break

    return shortcuts
    
def generate_empty_fieldset():
    return "<fieldset><legend>Type</legend>(No valid arc types)</fieldset>"

def kb_shortcuts_to_keymap(keyboard_shortcuts):
    """
    Given a dictionary mapping keys (single letter) to types (any
    string), returns the inverse mapping, processed for the
    generate_*_html functions.
    """
    type_to_key_map = {}
    for k in keyboard_shortcuts:
        type_to_key_map[keyboard_shortcuts[k]] = k
    return type_to_key_map

def generate_arc_type_html(projectconf, types, keyboard_shortcuts):
    keymap = kb_shortcuts_to_keymap(keyboard_shortcuts)
    return ("<fieldset><legend>Type</legend>" + 
            "\n".join(["\n".join(__generate_arc_input_and_label(t, projectconf.preferred_display_form(t), keymap)) for t in types]) +
            "</fieldset>")

def generate_textbound_type_html(projectconf, keyboard_shortcuts):
    keymap = kb_shortcuts_to_keymap(keyboard_shortcuts)

    return """<fieldset>
<legend>Entities</legend>
<fieldset>
<legend>Type</legend>
<div class="type_scroller">
""" + generate_entity_type_html(projectconf, keymap) + """
</div>
</fieldset>
</fieldset>
<fieldset>
<legend>Events</legend>
<fieldset>
<legend>Type</legend>
<div class="type_scroller">
""" + generate_event_type_html(projectconf, keymap) + """
</div>
</fieldset>
<fieldset id="span_mod_fset">
<legend>Attributes</legend>
""" + generate_event_attribute_html(projectconf, keymap) + """
</fieldset>
</fieldset>
"""

# XXX: Disabled
if False and __name__ == '__main__':
    import sys
    import message
    from projectconfig import ProjectConfiguration
    

    # debugging
    keymap = {
        'P': 'Protein',
        'E': 'Entity',
        'H': 'Hydroxylation',
        'R': 'Dehydroxylation',
        'O': 'Phosphorylation',
        'S': 'Dephosphorylation',
        'U': 'Ubiquitination',
        'B': 'Deubiquitination',
        'G': 'Glycosylation',
        'L': 'Deglycosylation',
        'A': 'Acetylation',
        'T': 'Deacetylation',
        'M': 'Methylation',
        'Y': 'Demethylation',
        'D': 'DNA_methylation',
        'N': 'DNA_demethylation',
        'C': 'Catalysis',
        }

    reverse_keymap = {}
    for k in keymap:
        reverse_keymap[keymap[k]] = k

    print generate_event_type_html(ProjectConfiguration("."), reverse_keymap)

    message.output_messages(sys.stdout)

if __name__ == '__main__':
    from projectconfig import ProjectConfiguration
    from jsonwrap import dumps
    directory = '/home/ninjin/public_html/brat/brat_test_data/epi'
    print dumps(get_span_types(directory))
