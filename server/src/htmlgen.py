#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

from __future__ import with_statement

'''
Server-side HTML generation-related functionality for
Brat Rapid Annotation Tool (brat)
'''

from cgi import escape as cgi_escape

from projectconfig import get_entity_type_hierarchy, get_event_type_hierarchy

def escape(s):
    return cgi_escape(s).replace('"', '&quot;');

def __generate_input_and_label(t, keymap, indent, disabled):
    l = []
    nst = t.replace(" ","_")
    if not disabled:
        dstr = ""
    else:
        dstr = ' disabled="disabled"'
    s  = indent+'    <input id="span_%s" name="span_type" type="radio" value="%s" %s/>' % (escape(nst.lower()),escape(nst),dstr)
    s += '<label for="span_%s">' % escape(nst.lower())

    # TODO: saner case/space-vs-underscore-insensitive processing
    kmt = t.lower().replace(" ", "_")
    if kmt not in keymap or kmt.find(keymap[kmt].lower()) == -1:
        s += '%s</label>' % escape(t)
    else:
        accesskey = keymap[kmt].lower()
        key_offset= kmt.find(accesskey)
        s += '%s<span class="accesskey">%s</span>%s</label>' % (escape(t[:key_offset]), escape(t[key_offset:key_offset+1]), escape(t[key_offset+1:]))
    l.append(s)
    return l
    

def __generate_node_html_lines(node, keymap, depth=0):
    # TODO: make this less exceptional, avoid magic values
    if node == "SEPARATOR":
        return ["<hr/>"]

    t = node.interface_term()
    # for debugging
    indent = " "*6*depth
    lines = []
    if len(node.children) == 0:
        # simple item
        lines.append(indent+'<div class="item">')
        lines.append(indent+'  <div class="item_content">')
        lines += __generate_input_and_label(t, keymap, indent, node.unused)
        lines.append(indent+'  </div>')
        lines.append(indent+'</div>')
    else:
        # collapsible item with children
        lines.append(indent+'<div class="item">')
        lines.append(indent+'  <div class="collapser open"></div>')
        lines.append(indent+'  <div class="item_content">')
        lines += __generate_input_and_label(t, keymap, indent, node.unused)
        lines.append(indent+'    <div class="collapsible open">')

        for n in node.children:
             lines += __generate_node_html_lines(n, keymap, depth+1)

        lines.append(indent+'    </div>')
        lines.append(indent+'  </div>')
        lines.append(indent+'</div>')

    return lines


def __generate_term_hierarchy_html(root_nodes, type_key_map):
    all_lines = []
    for n in root_nodes:
        all_lines += __generate_node_html_lines(n, type_key_map)
    return "\n".join(all_lines)

def generate_entity_type_html(directory, type_key_map):
    hierarchy = get_entity_type_hierarchy(directory)
    return __generate_term_hierarchy_html(hierarchy, type_key_map)
                                          
def generate_event_type_html(directory, type_key_map):
    hierarchy = get_event_type_hierarchy(directory)
    return __generate_term_hierarchy_html(hierarchy, type_key_map)

def generate_client_keymap(keyboard_shortcuts):
    client_keymap = {}
    for k in keyboard_shortcuts:
        # Note: all keymap processing is case-insensitive and treats space
        # and underscore ("_") interchangeably
        client_keymap[k] = 'span_'+keyboard_shortcuts[k].lower().replace(" ", "_")
    return client_keymap

def generate_textbound_type_html(directory, keyboard_shortcuts):
    # Note: all keymap processing is case-insensitive and treats space
    # and underscore ("_") interchangeably
    type_to_key_map = {}
    for k in keyboard_shortcuts:
        type_to_key_map[keyboard_shortcuts[k].lower().replace(" ", "_")] = k.lower()

    return """<fieldset>
<legend>Entities</legend>
<fieldset>
<legend>Type</legend>
<div class="type_scroller">
""" + generate_entity_type_html(directory, type_to_key_map) + """
</div>
</fieldset>
</fieldset>
<fieldset>
<legend>Events</legend>
<fieldset>
<legend>Type</legend>
<div class="type_scroller">
""" + generate_event_type_html(directory, type_to_key_map) + """</div>
</fieldset>
<fieldset id="span_mod_fset">
<legend>Modifications</legend>
<input id="span_mod_negation" type="checkbox" value="Negation"/>
<label for="span_mod_negation"><span class="accesskey">N</span>egation</label>
<input id="span_mod_speculation" type="checkbox" value="Speculation"/>
<label for="span_mod_speculation"><span class="accesskey">S</span>peculation</label>
</fieldset>
</fieldset>
"""

if __name__ == '__main__':
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

    print generate_event_type_html(".", reverse_keymap)
