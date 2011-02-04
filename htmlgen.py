#!/usr/bin/env python

'''
Server-side HTML generation-related functionality for
Brat Rapid Annotation Tool (brat)
'''

import re

# TODO: this whole thing is an ugly hack. Event types should be read
# from a proper ontology.

__event_type_hierarchy_filename = 'config_event_types.txt'

__default_event_type_hierarchy  = """GO:------- : !event
 GO:0005515 : protein binding
 GO:0010467 : gene expression"""

# special-purpose class for representing the structure of
# the event type hierarchy
class EventHierarchyNode:
    def __init__(self, GOid, GOtype):
        self.GOid, self.GOtype = GOid, GOtype
        self.unused = False
        if self.GOtype[0] == "!":
            self.GOtype = self.GOtype[1:]
            self.unused = True
        self.children = []
    def formtype(self):
        # abbreviated form of the GO type ala BioNLP ST
        
        t = self.GOtype
        if "protein modification" in t:
            # exception: don't abbrev mid-level strings
            return t[0].upper()+t[1:]
        else:
            # cut away initial "protein"
            t = re.sub(r'^protein ', '', t)
            t = t[0].upper()+t[1:]
            return t

def __read_event_hierarchy(input):
    root_nodes    = []
    last_node_at_depth = {}

    for l in input:
        # skip empties and lines starting with '#'
        if l.strip() == '' or re.match(r'^\s*#', l):
            continue

        m = re.match(r'^(\s*)(GO:\S+)\s*:\s*(.*?)\s*$', l)
        assert m, "Error parsing line: '%s'" % l
        indent, GOid, GOtype = m.groups()

        # depth in the ontology corresponds to the number of
        # spaces in the initial indent.
        depth = len(indent)

        n = EventHierarchyNode(GOid, GOtype)
        if depth == 0:
            # root level, no children assignments
            root_nodes.append(n)
        else:
            # assign as child of last node at the depth of the parent
            assert depth-1 in last_node_at_depth, "Error: no parent for %s" % l
            last_node_at_depth[depth-1].children.append(n)
        last_node_at_depth[depth] = n

    return root_nodes

def generate_span_type_html(type_key_map):
    global __event_type_hierarchy_filename

    try:
        f = open(__event_type_hierarchy_filename, 'r')
        event_type_hierarchy = f.read()
        f.close()
    except:
        # TODO: specific exceptions, useful error reporting
        # also to the user
        import sys
        print >> sys.stderr, 'brat htmlgen.py: error reading %s' % __event_type_hierarchy_filename
        # fall back to a minimal default hierarchy
        event_type_hierarchy = __default_event_type_hierarchy

    try:
        root_nodes = __read_event_hierarchy(event_type_hierarchy.split("\n"))
    except:
        # TODO: specific exceptions, useful error reporting
        # also to the user
        import sys
        print >> sys.stderr, 'brat htmlgen.py: error parsing event hierarchy.'
        # fall back to a minimum single choice
        root_nodes = [EventHierarchyNode("GO:-------", "event")]

    def input_and_label(t, indent, disabled):
        l = []
        nst = t.replace(" ","_")
        if not disabled:
            dstr = ""
        else:
            dstr = ' disabled="disabled"'
        l.append(indent+'    <input id="span_%s" name="span_type" type="radio" value="%s" %s/>' % (nst,nst,dstr))
        s = indent+'    <label for="span_%s">' % nst
        if t not in type_key_map or t.lower().find(type_key_map[t].lower()) == -1:
            s += '%s</label>' % t
        else:
            accesskey = type_key_map[t].lower()
            key_offset= t.lower().find(accesskey)
            s += '%s<span class="accesskey">%s</span>%s</label>' % (t[:key_offset], t[key_offset:key_offset+1], t[key_offset+1:])
        l.append(s)
        return l
    
    def generate_node_html_lines(node, depth=0):
        t   = node.formtype()
        indent = " "*6*depth
        lines = []
        if len(node.children) == 0:
            # simple item
            lines.append(indent+'<div class="item">')
            lines.append(indent+'  <div class="item_content">')
            lines += input_and_label(t, indent, node.unused)
            lines.append(indent+'  </div>')
            lines.append(indent+'</div>')
        else:
            # collapsible item with children
            lines.append(indent+'<div class="item">')
            lines.append(indent+'  <div class="collapser open"></div>')
            lines.append(indent+'  <div class="item_content">')
            lines += input_and_label(t, indent, node.unused)
            lines.append(indent+'    <div class="collapsible open">')

            for n in node.children:
                 lines += generate_node_html_lines(n, depth+1)

            lines.append(indent+'    </div>')
            lines.append(indent+'  </div>')
            lines.append(indent+'</div>')

        return lines

    all_lines = []
    for n in root_nodes:
        all_lines += generate_node_html_lines(n)
    return "\n".join(all_lines)

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

    print generate_span_type_html(reverse_keymap)
