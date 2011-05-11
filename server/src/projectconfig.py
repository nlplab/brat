#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:


'''
Per-project configuration functionality for
Brat Rapid Annotation Tool (brat)
'''

import re

from message import display_message

# TODO: replace with reading a proper ontology.

class InvalidProjectConfigException(Exception):
    pass

__entity_type_hierarchy_filename   = 'entity_types.conf'
__relation_type_hierarchy_filename = 'relation_types.conf'
__event_type_hierarchy_filename    = 'event_types.conf'
__abbreviation_filename            = 'abbreviations.conf'
__kb_shortcut_filename             = 'kb_shortcuts.conf'

# fallback defaults if configs not found
__default_entity_type_hierarchy = """
Protein
Entity"""

__default_event_type_hierarchy  = """
!event
 GO:0005515 | protein binding	Theme+:Protein
 GO:0010467 | gene expression	Theme:Protein"""

__default_relation_type_hierarchy = """
Equiv	Arg1:Protein, Arg2:Protein"""

__default_attribute_type_hierarchy = """
Affirmative	Arg:<EVENT>
Sure	Arg:<EVENT>"""

__default_abbreviations = """
Protein : Pro, P
Protein binding : Binding, Bind
Gene expression : Expression, Exp
Theme   : Th
"""

__default_kb_shortcuts = """
P	Protein
"""

def term_interface_form(t):
    """
    Returns a form of the term suitable for display to user.
    """

    # abbreviated form of the ontology term for display
    # to annotators, e.g. "protein phosphorylation"
    # -> "Phosphorylation"
    if re.match(r'^protein [a-z]*ation', t):
        # cut away initial "protein"
        t = re.sub(r'^protein ', '', t)
        t = t[0].upper()+t[1:]
        return t
    else:
        return t[0].upper()+t[1:]

def term_storage_form(t):
    """
    Returns a form of the the given term suitable for storage in standoff format.
    """
    return term_interface_form(t).replace(" ","_")


class TypeHierarchyNode:
    """
    Represents a node in a simple hierarchical ontology.
    """
    def __init__(self, terms, args):
        self.terms, self.args = terms, args

        if len(terms) == 0 or len([t for t in terms if t == ""]) != 0:
            display_message("Empty term in type configuration" % (a, args), "debug", -1)
            raise InvalidProjectConfigException

        # unused if any of the terms marked with "!"
        self.unused = False
        for i in range(len(self.terms)):
            if self.terms[i][0] == "!":
                self.terms[i]= self.terms[i][1:]
                self.unused = True
        self.children = []

        # by convention, the last of the listed terms is used
        # as the primary term
        self.primary_term = self.terms[-1]

        # TODO: cleaner and more localized parsing
        self.arguments = []
        self.mandatory_arguments = []
        self.multiple_allowed_arguments = []
        self.roles_by_type = {}
        for a in self.args:
            a = a.strip()
            m = re.match(r'^(.*?):(.*)$', a)
            if not m:
                display_message("Failed to parse argument %s (args: %s)" % (a, args), "debug", -1)
                raise InvalidProjectConfigException
            role, atypes = m.groups()

            if role[-1:] not in ("?", "*"):
                mandatory_role = True
            else:
                mandatory_role = False

            if role[-1:] in ("*", "+"):
                multiple_allowed = True
            else:
                multiple_allowed = False

            if role[-1:] in ("?", "*", "+"):
                role = role[:-1]

            if mandatory_role:
                self.mandatory_arguments.append(role)

            if multiple_allowed:
                self.multiple_allowed_arguments.append(role)

            for atype in atypes.split("|"):
                if atype.strip() == "":
                    raise InvalidProjectConfigException
                atype = term_storage_form(atype)

                self.arguments.append((role, atype))

                if atype not in self.roles_by_type:
                    self.roles_by_type[atype] = []
                self.roles_by_type[atype].append(role)

    def __norm(self, t):
        return t.lower().replace(" ", "_")

    def storage_term(self):
        return term_storage_form(self.primary_term)

    def interface_term(self):
        return term_interface_form(self.primary_term)


def __read_term_hierarchy(input):
    root_nodes    = []
    last_node_at_depth = {}

    macros = {}
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

        # interpret lines of the format <STR1>=STR2 as "macro"
        # definitions, defining <STR1> as a placeholder that should be
        # replaced with STR2 whevever it occurs.
        m = re.match(r'^<([a-zA-Z_-]+)>=\s*(.*?)\s*$', l)
        if m:
            name, value = m.groups()
            if name in ("ANY", "ENTITY", "RELATION", "EVENT", "NONE"):
                display_message("Error: cannot redefine <%s> in configuration, it is a reserved name." % name)
                # TODO: proper exception
                assert False
            else:
                macros["<%s>" % name] = value
            continue

        # macro expansion
        for n in macros:
            l = l.replace(n, macros[n])
        
        m = re.match(r'^(\s*)([^\t]+)(?:\t(.*))?$', l)
        assert m, "Error parsing line: '%s'" % l
        indent, terms, args = m.groups()
        terms = [t.strip() for t in terms.split("|") if t.strip() != ""]
        if args is None or args.strip() == "":
            args = []
        else:
            args = [a.strip() for a in args.split(",") if a.strip() != ""]

        # depth in the ontology corresponds to the number of
        # spaces in the initial indent.
        depth = len(indent)

        n = TypeHierarchyNode(terms, args)
        if depth == 0:
            # root level, no children assignments
            root_nodes.append(n)
        else:
            # assign as child of last node at the depth of the parent
            assert depth-1 in last_node_at_depth, "Error: no parent for '%s'" % l
            last_node_at_depth[depth-1].children.append(n)
        last_node_at_depth[depth] = n

    return root_nodes

def __read_or_default(filename, default):
    try:
        f = open(filename, 'r')
        r = f.read()
        f.close()
        return r
    except:
        # TODO: specific exception handling and reporting
        return default

def __parse_term_hierarchy(hierarchy, default, source):
    try:
        root_nodes = __read_term_hierarchy(hierarchy.split("\n"))
    except:
        # TODO: specific exception handling
        display_message("Project configuration: error parsing types from %s. Configuration may be wrong." % source, "warning", 5)
        root_nodes = default
    return root_nodes

def __parse_abbreviations(abbrevstr, default, source):
    try:
        abbreviations = {}
        for l in abbrevstr.split("\n"):
            l = l.strip()
            if l == "" or l[:1] == "#":
                continue
            full, abbrevs = l.split(":")
            abbreviations[full.strip()] = [a.strip() for a in abbrevs.split(",")]
    except:
        # TODO: specific exception handling
        display_message("Project configuration: error parsing abbreviations from %s. Configuration may be wrong." % source, "warning", 5)
        abbreviations = default
    return abbreviations

def __parse_kb_shortcuts(shortcutstr, default, source):
    try:
        shortcuts = {}
        for l in shortcutstr.split("\n"):
            l = l.strip()
            if l == "" or l[:1] == "#":
                continue
            key, type = re.split(r'[ \t]+', l)
            # TODO: check dups?
            shortcuts[key] = type
    except:
        # TODO: specific exception handling
        display_message("Project configuration: error parsing keyboard shortcuts from %s. Configuration may be wrong." % source, "warning", 5)
        shortcuts = default
    return shortcuts

def __read_first_in_directory_tree(directory, filename):
    # config will not be available command-line invocations;
    # in these cases search whole tree
    try:
        from config import BASE_DIR
    except:
        BASE_DIR = "/"
    from os.path import split, join

    source, result = None, None

    # check from the given directory and parents, but not above BASE_DIR
    if directory is not None:
        # TODO: this check may fail; consider "foo//bar/data"
        while BASE_DIR in directory:
            source = join(directory, filename)
            result = __read_or_default(source, None)
            if result is not None:
                break
            directory = split(directory)[0]

    return (result, source)

def __get_type_hierarchy(directory, filename, default_hierarchy, min_hierarchy):

    type_hierarchy, source = __read_first_in_directory_tree(directory, filename)

    if type_hierarchy is None:
        # didn't get one; try default dir and fall back to the default
        # hierarchy
        type_hierarchy = __read_or_default(filename, default_hierarchy)
        if type_hierarchy == default_hierarchy:
            source = "[default hierarchy]"
        else:
            source = filename
        
    # try to parse what we got, fall back to minimal hierarchy
    root_nodes = __parse_term_hierarchy(type_hierarchy, min_hierarchy, source)

    return root_nodes

def __get_abbreviations(directory, filename, default_abbrevs, min_abbrevs):

    abbrevstr, source = __read_first_in_directory_tree(directory, filename)

    if abbrevstr is None:
        abbrevstr = __read_or_default(filename, default_abbrevs)
        if abbrevstr == default_abbrevs:
            source = "[default abbreviations]"
        else:
            source = filename

    abbreviations = __parse_abbreviations(abbrevstr, min_abbrevs, source)
    return abbreviations

def __get_kb_shortcuts(directory, filename, default_shortcuts, min_shortcuts):

    shortcutstr, source = __read_first_in_directory_tree(directory, filename)

    if shortcutstr is None:
        shortcutstr = __read_or_default(filename, default_shortcuts)
        if shortcutstr == default_shortcuts:
            source = "[default kb_shortcuts]"
        else:
            source = filename

    kb_shortcuts = __parse_kb_shortcuts(shortcutstr, min_shortcuts, source)
    return kb_shortcuts

# Configuration lookup specifications, each a triple (FILENAME,
# HIERARCHY_STR, HIERARCHY). The directory path is searched for
# FILENAME, and if none is found, the system falls attempts to parse
# HIERARCHY_STR for the hierarchy; if that fails, HIERARCHY is used
# directly.

__entity_type_lookups = (
    __entity_type_hierarchy_filename,
    __default_entity_type_hierarchy,
    [TypeHierarchyNode(["protein"], [])],
)

__relation_type_lookups = (
    __relation_type_hierarchy_filename,
    __default_relation_type_hierarchy,
    [TypeHierarchyNode(["Equiv"], ["Arg1:Protein", "Arg2:Protein"])],
)

__event_type_lookups = (
    __event_type_hierarchy_filename,
    __default_event_type_hierarchy,
    [TypeHierarchyNode(["event"], ["Theme:Protein"])],
)

def __get_type_hierarchy_with_cache(directory, cache, lookups):
    if directory not in cache:
        cache[directory] = __get_type_hierarchy(directory, *lookups)
    return cache[directory]

# Caching methods to avoid re-reading on every invocation of getters.
# Outside of ProjectConfiguration class to minimize reads when
# multiple configs are instantiated.

def get_entity_type_hierarchy(directory):
    cache, lookups = get_entity_type_hierarchy.__cache, __entity_type_lookups
    return __get_type_hierarchy_with_cache(directory, cache, lookups)
get_entity_type_hierarchy.__cache = {}

def get_relation_type_hierarchy(directory):
    cache, lookups = get_relation_type_hierarchy.__cache, __relation_type_lookups
    return __get_type_hierarchy_with_cache(directory, cache, lookups)
get_relation_type_hierarchy.__cache = {}

def get_event_type_hierarchy(directory):
    cache, lookups = get_event_type_hierarchy.__cache, __event_type_lookups
    return __get_type_hierarchy_with_cache(directory, cache, lookups)
get_event_type_hierarchy.__cache = {}

def get_attribute_type_hierarchy(directory):
    cache, lookups = get_attribute_type_hierarchy.__cache, __attribute_type_lookups
    return __get_type_hierarchy_with_cache(directory, cache, lookups)
get_attribute_type_hierarchy.__cache = {}

def get_abbreviations(directory):
    cache = get_abbreviations.__cache
    if directory not in cache:
        a = __get_abbreviations(directory,
                                __abbreviation_filename,
                                __default_abbreviations,
                                { "Protein" : [ "Pro", "P" ], "Theme" : [ "Th" ] })
        cache[directory] = a

    return cache[directory]
get_abbreviations.__cache = {}

def get_kb_shortcuts(directory):
    cache = get_kb_shortcuts.__cache
    if directory not in cache:
        a = __get_kb_shortcuts(directory,
                                __kb_shortcut_filename,
                                __default_kb_shortcuts,
                               { "P" : "Positive_regulation" })
        cache[directory] = a

    return cache[directory]
get_kb_shortcuts.__cache = {}

def __collect_type_list(node, collected):
    if node == "SEPARATOR":
        return collected

    collected.append(node)

    for c in node.children:
        __collect_type_list(c, collected)

    return collected

def __type_hierarchy_to_list(hierarchy):
    root_nodes = hierarchy
    types = []
    for n in root_nodes:
        __collect_type_list(n, types)
    return types

def pc_get_entity_type_list(directory):
    cache = pc_get_entity_type_list.__cache
    if directory not in cache:
        cache[directory] = __type_hierarchy_to_list(get_entity_type_hierarchy(directory))
    return cache[directory]
pc_get_entity_type_list.__cache = {}

def pc_get_event_type_list(directory):
    cache = pc_get_event_type_list.__cache
    if directory not in cache:
        cache[directory] = __type_hierarchy_to_list(get_event_type_hierarchy(directory))
    return cache[directory]
pc_get_event_type_list.__cache = {}

def pc_get_relation_type_list(directory):
    cache = pc_get_relation_type_list.__cache
    if directory not in cache:
        cache[directory] = __type_hierarchy_to_list(get_relation_type_hierarchy(directory))
    return cache[directory]
pc_get_relation_type_list.__cache = {}

def pc_get_node_by_term(directory, term):
    cache = pc_get_node_by_term.__cache
    if directory not in cache:
        d = {}
        for e in pc_get_entity_type_list(directory) + pc_get_event_type_list(directory):
            t = e.storage_term()
            if t in d:
                display_message("Project configuration: interface term %s matches multiple types (incl. '%s' and '%s'). Configuration may be wrong." % (t, d[t].storage_term(), e.storage_term()), "warning", 5)
            d[t] = e
        cache[directory] = d

    return cache[directory].get(term, None)
pc_get_node_by_term.__cache = {}

def pc_get_relations_by_arg1(directory, term):
    cache = pc_get_relations_by_arg1.__cache
    if directory not in cache:
        cache[directory] = {}
    rels = []
    if term not in cache[directory]:
        for r in pc_get_relation_type_list(directory):
            arg1s = [a for a in r.arguments if a[0] == "Arg1"]
            if len(arg1s) != 1:
                display_message("Relation type %s lacking Arg1. Configuration may be wrong." % type, "warning")
                continue
            arg1 = arg1s[0]
            if arg1[1] == "<ANY>" or arg1[1] == term:
                rels.append(r)
        cache[directory] = rels
    return cache[directory]
pc_get_relations_by_arg1.__cache = {}

# fallback for missing or partial config: these are highly likely to
# be entity (as opposed to an event or relation) types.
# TODO: remove this workaround once the configs stabilize.
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

# helper
def unique_preserve_order(iterable):
    seen = set()
    uniqued = []
    for i in iterable:
        if i not in seen:
            seen.add(i)
            uniqued.append(i)
    return uniqued

class ProjectConfiguration(object):
    def __init__(self, directory):
        # debugging
        if directory[:1] != "/":
            display_message("Warning: project config received relative directory, configuration may not be found.", "debug", -1)
        self.directory = directory

    def mandatory_arguments(self, type):
        """
        Returns the mandatory arguments types that must be present for
        an annotation of the given type.
        """
        node = pc_get_node_by_term(self.directory, type)
        if node is None:
            display_message("Project configuration: unknown type %s. Configuration may be wrong." % type, "warning")
            return []
        return node.mandatory_arguments

    def multiple_allowed_arguments(self, type):
        """
        Returns the arguments types that are allowed to be filled more
        than once for an annotation of the given type.
        """
        node = pc_get_node_by_term(self.directory, type)
        if node is None:
            display_message("Project configuration: unknown type %s. Configuration may be wrong." % type, "warning")
            return []
        return node.multiple_allowed_arguments

    def arc_types_from(self, from_ann):
        return self.arc_types_from_to(from_ann)

    def arc_types_from_to(self, from_ann, to_ann="<ANY>"):
        """
        Returns the possible arc types that can connect an annotation
        of type from_ann to an annotation of type to_ann.
        If to_ann has the value \"<ANY>\", returns all possible arc types.
        """

        from_node = pc_get_node_by_term(self.directory, from_ann)

        relations_from = pc_get_relations_by_arg1(self.directory, from_ann)

        if from_node is None:
            display_message("Project configuration: unknown type %s. Configuration may be wrong." % from_ann, "warning")
            return []
        if to_ann == "<ANY>":
            return unique_preserve_order([role for role, type in from_node.arguments] + [r.primary_term for r in relations_from])

        # specific hits
        if to_ann not in from_node.roles_by_type:
            types = []
        else:
            types = from_node.roles_by_type[to_ann]

        # generic arguments
        if self.is_event_type(to_ann) and '<EVENT>' in from_node.roles_by_type:
            types += from_node.roles_by_type['<EVENT>']
        if self.is_physical_entity_type(to_ann) and '<ENTITY>' in from_node.roles_by_type:
            types += from_node.roles_by_type['<ENTITY>']

        # relations
        # TODO: handle generic '<ENTITY>' (like '<EVENT>' above)
        for r in relations_from:
            if to_ann in r.roles_by_type and "Arg2" in r.roles_by_type[to_ann]:
                types.append(r.primary_term)

        return unique_preserve_order(types)

    def get_abbreviations(self):
        return get_abbreviations(self.directory)

    def get_kb_shortcuts(self):
        return get_kb_shortcuts(self.directory)

    def get_event_types(self):
        return [t.storage_term() for t in pc_get_event_type_list(self.directory)]

    def get_relation_types(self):
        return [t.storage_term() for t in pc_get_relation_type_list(self.directory)]        

    def get_entity_types(self):
        return [t.storage_term() for t in pc_get_entity_type_list(self.directory)]

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
