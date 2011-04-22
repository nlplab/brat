#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:


'''
Per-project configuration functionality
'''

import re

from message import display_message

# TODO: replace with reading a proper ontology.

class InvalidProjectConfigException(Exception):
    pass

__abbreviation_filename          = 'abbreviations.conf'

# fallback defaults if configs not found
__default_abbreviations = """
Protein : Pro, P
Protein binding : Binding, Bind
Gene expression : Expression, Exp
Theme   : Th
"""

# cache to avoid re-reading on every invocation of getters.
# outside of ProjectConfiguration class to minimize reads
# when multiple configs are in play.
__directory_abbreviations = {}

def __read_or_default(filename, default):
    try:
        f = open(filename, 'r')
        r = f.read()
        f.close()
        return r
    except:
        # TODO: specific exception handling and reporting
        return default

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

def __read_first_in_directory_tree(directory, filename):
    from config import BASE_DIR
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

def get_abbreviations(directory):
    global __directory_abbreviations

    if directory not in __directory_abbreviations:
        a = __get_abbreviations(directory,
                                __abbreviation_filename,
                                __default_abbreviations,
                                { "Protein" : [ "Pro", "P" ], "Theme" : [ "Th" ] })
        __directory_abbreviations[directory] = a

    return __directory_abbreviations[directory]

class ProjectConfiguration(object):
    def __init__(self, directory):
        # debugging
        if directory[:1] != "/":
            display_message("Warning: project config received relative directory, configuration may not be found.", "debug", -1)
        self.directory = directory

    def get_abbreviations(self):
        return get_abbreviations(self.directory)

    def get_event_types(self):
        return [t.storage_term() for t in pc_get_event_type_list(self.directory)]

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
