#!/usr/bin/env python

'''
Server-side HTML generation-related functionality for
Brat Rapid Annotation Tool (brat)
'''

import re

# TODO: this whole thing is an ugly hack. Event types should be read
# from a proper ontology.

__event_type_hierarchy_filename  = 'event_types.conf'
__entity_type_hierarchy_filename = 'entity_types.conf'

__default_event_type_hierarchy  = """
generic:------- : !event
 GO:0005515 : protein binding
 GO:0010467 : gene expression"""

__default_entity_type_hierarchy = """
generic:------- : Protein
generic:------- : Entity"""

# special-purpose class for representing a node in a simple
# hierarchical ontology
class TypeHierarchyNode:
    def __init__(self, ontology_name, ontology_id, ontology_term):
        self.ontology_name, self.ontology_id, self.ontology_term = ontology_name, ontology_id, ontology_term
        self.unused = False
        if self.ontology_term[0] == "!":
            self.ontology_term = self.ontology_term[1:]
            self.unused = True
        self.children = []
        
    def display_term(self):
        t = self.ontology_term

        if self.ontology_name == "GO":
            # abbreviated form of the ontology term for display
            # to annotators, e.g. "protein phosphorylation"
            # -> "Phosphorylation"

            if "protein modification" in t:
                # exception: don't abbrev mid-level strings
                return t[0].upper()+t[1:]
            else:
                # cut away initial "protein"
                t = re.sub(r'^protein ', '', t)
                t = t[0].upper()+t[1:]
                return t
        else:
            return t[0].upper()+t[1:]

def __read_term_hierarchy(input):
    root_nodes    = []
    last_node_at_depth = {}

    for l in input:
        # skip empties and lines starting with '#'
        if l.strip() == '' or re.match(r'^\s*#', l):
            continue

        # interpret lines of only hyphens as separators
        # for display
        if re.match(r'^\s*-+\s*$', l):
            # TODO: proper placeholder and placing
            root_nodes.append("SEPARATOR")
            continue

        m = re.match(r'^(\s*)(\S+):(\S+)\s*:\s*(.*?)\s*$', l)
        assert m, "Error parsing line: '%s'" % l
        indent, ontology_name, ontology_id, ontology_term = m.groups()

        # depth in the ontology corresponds to the number of
        # spaces in the initial indent.
        depth = len(indent)

        n = TypeHierarchyNode(ontology_name, ontology_id, ontology_term)
        if depth == 0:
            # root level, no children assignments
            root_nodes.append(n)
        else:
            # assign as child of last node at the depth of the parent
            assert depth-1 in last_node_at_depth, "Error: no parent for %s" % l
            last_node_at_depth[depth-1].children.append(n)
        last_node_at_depth[depth] = n

    return root_nodes


def __read_term_hierarchy_file(filename, default):
    try:
        f = open(filename, 'r')
        term_hierarchy = f.read()
        f.close()
    except:
        # TODO: specific exceptions, useful error reporting
        # also to the user
        import sys
        print >> sys.stderr, 'brat htmlgen.py: error reading %s' % filename
        term_hierarchy = default
    return term_hierarchy


def __parse_term_hierarchy(hierarchy, default):
    try:
        root_nodes = __read_term_hierarchy(hierarchy.split("\n"))
    except:
        # TODO: specific exceptions, useful error reporting
        # also to the user
        import sys
        print >> sys.stderr, 'brat htmlgen.py: error parsing term hierarchy.'
        root_nodes = default
    return root_nodes


def __generate_input_and_label(t, keymap, indent, disabled):
    l = []
    nst = t.replace(" ","_")
    if not disabled:
        dstr = ""
    else:
        dstr = ' disabled="disabled"'
    s  = indent+'    <input id="span_%s" name="span_type" type="radio" value="%s" %s/>' % (nst.lower(),nst,dstr)
    s += indent+'<label for="span_%s">' % nst.lower()

    # TODO: saner case/space-vs-underscore-insensitive processing
    kmt = t.lower().replace(" ", "_")
    if kmt not in keymap or kmt.find(keymap[kmt].lower()) == -1:
        s += '%s</label>' % t
    else:
        accesskey = keymap[kmt].lower()
        key_offset= kmt.find(accesskey)
        s += '%s<span class="accesskey">%s</span>%s</label>' % (t[:key_offset], t[key_offset:key_offset+1], t[key_offset+1:])
    l.append(s)
    return l
    

def __generate_node_html_lines(node, keymap, depth=0):
    # TODO: make this less exceptional, avoid magic values
    if node == "SEPARATOR":
        return ["<hr/>"]

    t = node.display_term()
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


def __generate_term_hierarchy_html(directory, type_key_map,
                                   filename, default_hierarchy, min_hierarchy):
    type_hierarchy = None

    if directory is not None:
        # try to find a config file in the directory
        import os
        fn = os.path.join(directory, filename)
        type_hierarchy = __read_term_hierarchy_file(fn, None)

    if type_hierarchy is None:
        # if we didn't get a directory-specific one, try default dir
        # and fall back to the default hierarchy
        type_hierarchy = __read_term_hierarchy_file(filename, default_hierarchy)

    # try to parse what we got, fall back to minimal hierarchy
    root_nodes = __parse_term_hierarchy(type_hierarchy, min_hierarchy)
    
    all_lines = []
    for n in root_nodes:
        all_lines += __generate_node_html_lines(n, type_key_map)
    return "\n".join(all_lines)


def generate_entity_type_html(directory, type_key_map):
    return __generate_term_hierarchy_html(directory, type_key_map, 
                                          __entity_type_hierarchy_filename,
                                          __default_entity_type_hierarchy,
                                          [TypeHierarchyNode("generic", "-------", "protein")])

def generate_event_type_html(directory, type_key_map):
    return __generate_term_hierarchy_html(directory, type_key_map, 
                                          __event_type_hierarchy_filename,
                                          __default_event_type_hierarchy,
                                          [TypeHierarchyNode("generic", "-------", "event")])

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

    print generate_event_type_html(reverse_keymap)
