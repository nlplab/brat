#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:


'''
Per-project configuration functionality for
Brat Rapid Annotation Tool (brat)
'''

import re

from message import display_message

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

# caches to avoid re-reading on every invocation of getters
__directory_entity_type_hierarchy = {}
__directory_event_type_hierarchy = {}
__directory_entity_types = {}
__directory_event_types = {}

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

    def storage_term(self):
        # currently same as display term but replacing
        # space with underscore so that the type can be
        # stored in the standard standoff
        return self.display_term().replace(" ","_")
        
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
        # TODO: specific exception handling
        term_hierarchy = default
    return term_hierarchy


def __parse_term_hierarchy(hierarchy, default, source):
    try:
        root_nodes = __read_term_hierarchy(hierarchy.split("\n"))
    except:
        # TODO: specific exception handling
        display_message("Project configuration: error parsing types from %s. Configuration may be wrong." % source, "warning", 5)
        root_nodes = default
    return root_nodes

def __get_type_hierarchy(directory, filename, default_hierarchy, min_hierarchy):
    type_hierarchy = None

    if directory is not None:
        # try to find a config file in the directory
        import os
        fn = os.path.join(directory, filename)
        source = fn
        type_hierarchy = __read_term_hierarchy_file(fn, None)

    if type_hierarchy is None:
        # if we didn't get a directory-specific one, try default dir
        # and fall back to the default hierarchy
        #
        source = filename
        # too noisy
        #display_message("Project configuration: type config %s not found in %s" % (filename, directory))
        type_hierarchy = __read_term_hierarchy_file(filename, default_hierarchy)
        if type_hierarchy == default_hierarchy:
            source = "[default hierarchy]"
        
    # try to parse what we got, fall back to minimal hierarchy
    root_nodes = __parse_term_hierarchy(type_hierarchy, min_hierarchy, source)

    return root_nodes

def get_entity_type_hierarchy(directory):
    global __directory_entity_type_hierarchy

    if directory not in __directory_entity_type_hierarchy:
        h = __get_type_hierarchy(directory,
                                 __entity_type_hierarchy_filename,
                                 __default_entity_type_hierarchy,
                                 [TypeHierarchyNode("generic", "-------", "protein")])
        __directory_entity_type_hierarchy[directory] = h

    return __directory_entity_type_hierarchy[directory]
    
     
def get_event_type_hierarchy(directory):
    global __directory_event_type_hierarchy

    if directory not in __directory_event_type_hierarchy:
        h =  __get_type_hierarchy(directory,
                                  __event_type_hierarchy_filename,
                                  __default_event_type_hierarchy,
                                  [TypeHierarchyNode("generic", "-------", "event")])
        __directory_event_type_hierarchy[directory] = h

    return __directory_event_type_hierarchy[directory]

def __collect_types(node, collected):
    if node == "SEPARATOR":
        return collected

    t = node.storage_term()

    if t not in collected:
        collected.append(t)

    for c in node.children:
        __collect_types(c, collected)

    return collected

def pc_get_entity_types(directory):
    global __directory_entity_types

    if directory not in __directory_entity_types:
        root_nodes = get_entity_type_hierarchy(directory)
        types = []
        for n in root_nodes:
            __collect_types(n, types)
        __directory_entity_types[directory] = types

    return __directory_entity_types[directory]

def pc_get_event_types(directory):
    global __directory_event_types

    if directory not in __directory_event_types:
        root_nodes = get_event_type_hierarchy(directory)
        types = []
        for n in root_nodes:
            __collect_types(n, types)
        __directory_event_types[directory] = types

    return __directory_event_types[directory]

# fallback for missing or partial config: these are highly likely to
# be entity (as opposed to an event or relation) types.
very_likely_physical_entity_types = [
    'Protein',
    'Entity',
    'Organism',
    'Chemical',
    'Two-component-system',
    'Regulon-operon',
    # for more PTM annotation
    'Protein_family_or_group',
    'DNA_domain_or_region',
    'Protein_domain_or_region',
    'Amino_acid_monomer',
    'Carbohydrate',
    # for AZ corpus
    'Cell_type',
    'Drug_or_compound',
    'Gene_or_gene_product',
    'Pathway',
    'Tissue',
    #'Not_sure',
    #'Other',
    'Other_pharmaceutical_agent',
    ]

class ProjectConfiguration(object):
    def __init__(self, directory):
        self.directory = directory

    def get_event_types(self):
        return pc_get_event_types(self.directory)

    def get_entity_types(self):
        return pc_get_entity_types(self.directory)

    def is_physical_entity_type(self, t):
        # TODO: remove this temporary hack
        if t in very_likely_physical_entity_types:
            return True

        return t in self.get_entity_types()

    def is_event_type(self, t):
        return t in self.get_event_types()

    def type_category(self, t):
        """
        Returns the category of the given type t.
        The categories can be compared for equivalence but offer
        no other interface.
        """
        if self.is_physical_entity_type(t):
            return "PHYSICAL"
        elif self.is_event_type(t):
            return "EVENT"
        else:
            # TODO:
            return "OTHER"
