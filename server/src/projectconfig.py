#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:


"""Per-project configuration functionality for Brat Rapid Annotation Tool
(brat)

Author:     Pontus Stenetorp    <pontus is s u-tokyo ac jp>
Author:     Sampo Pyysalo       <smp is s u-tokyo ac jp>
Author:     Illes Solt          <solt tmit bme hu>
Version:    2011-08-15
"""

import re
import sys
import urllib.parse  # TODO reduce scope
import urllib.robotparser  # TODO reduce scope

from annotation import open_textfile
from message import Messager

ENTITY_CATEGORY, EVENT_CATEGORY, RELATION_CATEGORY, UNKNOWN_CATEGORY = range(
    4)


class InvalidProjectConfigException(Exception):
    pass


# names of files in which various configs are found
__access_control_filename = 'acl.conf'
__annotation_config_filename = 'annotation.conf'
__visual_config_filename = 'visual.conf'
__tools_config_filename = 'tools.conf'
__kb_shortcut_filename = 'kb_shortcuts.conf'

# annotation config section name constants
ENTITY_SECTION = "entities"
RELATION_SECTION = "relations"
EVENT_SECTION = "events"
ATTRIBUTE_SECTION = "attributes"

# aliases for config section names
SECTION_ALIAS = {
    "spans": ENTITY_SECTION,
}

__expected_annotation_sections = (
    ENTITY_SECTION,
    RELATION_SECTION,
    EVENT_SECTION,
    ATTRIBUTE_SECTION)
__optional_annotation_sections = []

# visual config section name constants
OPTIONS_SECTION = "options"
LABEL_SECTION = "labels"
DRAWING_SECTION = "drawing"

__expected_visual_sections = (OPTIONS_SECTION, LABEL_SECTION, DRAWING_SECTION)
__optional_visual_sections = [OPTIONS_SECTION]

# tools config section name constants
SEARCH_SECTION = "search"
ANNOTATORS_SECTION = "annotators"
DISAMBIGUATORS_SECTION = "disambiguators"
NORMALIZATION_SECTION = "normalization"

__expected_tools_sections = (
    OPTIONS_SECTION,
    SEARCH_SECTION,
    ANNOTATORS_SECTION,
    DISAMBIGUATORS_SECTION,
    NORMALIZATION_SECTION)
__optional_tools_sections = (
    OPTIONS_SECTION,
    SEARCH_SECTION,
    ANNOTATORS_SECTION,
    DISAMBIGUATORS_SECTION,
    NORMALIZATION_SECTION)

# special relation types for marking which spans can overlap
# ENTITY_NESTING_TYPE used up to version 1.3, now deprecated
ENTITY_NESTING_TYPE = "ENTITY-NESTING"
# TEXTBOUND_OVERLAP_TYPE used from version 1.3 onward
TEXTBOUND_OVERLAP_TYPE = "<OVERLAP>"
SPECIAL_RELATION_TYPES = set([ENTITY_NESTING_TYPE,
                              TEXTBOUND_OVERLAP_TYPE])
OVERLAP_TYPE_ARG = '<OVL-TYPE>'

# visual config default value names
VISUAL_SPAN_DEFAULT = "SPAN_DEFAULT"
VISUAL_ARC_DEFAULT = "ARC_DEFAULT"
VISUAL_ATTR_DEFAULT = "ATTRIBUTE_DEFAULT"

# visual config attribute name lists
SPAN_DRAWING_ATTRIBUTES = ['fgColor', 'bgColor', 'borderColor']
ARC_DRAWING_ATTRIBUTES = ['color', 'dashArray', 'arrowHead', 'labelArrow']
ATTR_DRAWING_ATTRIBUTES = [
    'glyphColor',
    'box',
    'dashArray',
    'glyph',
    'position']

# fallback defaults if config files not found
__default_configuration = """
[entities]
Protein

[relations]
Equiv	Arg1:Protein, Arg2:Protein, <REL-TYPE>:symmetric-transitive

[events]
Protein_binding|GO:0005515	Theme+:Protein
Gene_expression|GO:0010467	Theme:Protein

[attributes]
Negation	Arg:<EVENT>
Speculation	Arg:<EVENT>
"""

__default_visual = """
[labels]
Protein | Protein | Pro | P
Protein_binding | Protein binding | Binding | Bind
Gene_expression | Gene expression | Expression | Exp
Theme | Theme | Th

[drawing]
Protein	bgColor:#7fa2ff
SPAN_DEFAULT	fgColor:black, bgColor:lightgreen, borderColor:black
ARC_DEFAULT	color:black
ATTRIBUTE_DEFAULT	glyph:*
"""

__default_tools = """
[search]
google     <URL>:http://www.google.com/search?q=%s
"""

__default_kb_shortcuts = """
P	Protein
"""

__default_access_control = """
User-agent: *
Allow: /
Disallow: /hidden/

User-agent: guest
Disallow: /confidential/
"""

# Reserved strings with special meanings in configuration.
reserved_config_name = [
    "ANY",
    "ENTITY",
    "RELATION",
    "EVENT",
    "NONE",
    "EMPTY",
    "REL-TYPE",
    "URL",
    "URLBASE",
    "GLYPH-POS",
    "DEFAULT",
    "NORM",
    "OVERLAP",
    "OVL-TYPE",
    "INHERIT"]
# TODO: "GLYPH-POS" is no longer used, warn if encountered and
# recommend to use "position" instead.
reserved_config_string = ["<%s>" % n for n in reserved_config_name]

# Magic string to use to represent a separator in a config
SEPARATOR_STR = "SEPARATOR"


def normalize_to_storage_form(t):
    """Given a label, returns a form of the term that can be used for disk
    storage.

    For example, space can be replaced with underscores to allow use
    with space-separated formats.
    """
    if t not in normalize_to_storage_form.__cache:
        # conservative implementation: replace any space with
        # underscore, replace unicode accented characters with
        # non-accented equivalents, remove others, and finally replace
        # all characters not in [a-zA-Z0-9_-] with underscores.

        import re
        import unicodedata

        n = t.replace(" ", "_")
        if isinstance(n, str):
            unicodedata.normalize('NFKD', n).encode('ascii', 'ignore')
        n = re.sub(r'[^a-zA-Z0-9_-]', '_', n)

        normalize_to_storage_form.__cache[t] = n

    return normalize_to_storage_form.__cache[t]


normalize_to_storage_form.__cache = {}


class TypeHierarchyNode:
    """Represents a node in a simple (possibly flat) hierarchy.

    Each node is associated with a set of terms, one of which (the
    storage_form) matches the way in which the type denoted by the
    node is referenced to in data stored on disk and in client-server
    communications. This term is guaranteed to be in "storage form" as
    defined by normalize_to_storage_form().

    Each node may be associated with one or more "arguments", which
    are (multivalued) key:value pairs. These determine various characteristics
    of the node, but their interpretation depends on the hierarchy the
    node occupies: for example, for events the arguments correspond to
    event arguments.
    """

    def __init__(self, terms, args=[]):
        self.terms, self.args = terms, args

        if len(terms) == 0 or len([t for t in terms if t == ""]) != 0:
            Messager.debug("Empty term in configuration", duration=-1)
            raise InvalidProjectConfigException

        # unused if any of the terms marked with "!"
        self.unused = False
        for i in range(len(self.terms)):
            if self.terms[i][0] == "!":
                self.terms[i] = self.terms[i][1:]
                self.unused = True
        self.children = []

        # The first of the listed terms is used as the primary term for
        # storage (excepting for "special" config-only types). Due to
        # format restrictions, this form must not have e.g. space or
        # various special characters.
        if self.terms[0] not in SPECIAL_RELATION_TYPES:
            self.__primary_term = normalize_to_storage_form(self.terms[0])
        else:
            self.__primary_term = self.terms[0]
        # TODO: this might not be the ideal place to put this warning
        if self.__primary_term != self.terms[0]:
            Messager.warning(
                "Note: in configuration, term '%s' is not appropriate for storage (should match '^[a-zA-Z0-9_-]*$'), using '%s' instead. (Revise configuration file to get rid of this message. Terms other than the first are not subject to this restriction.)" %
                (self.terms[0], self.__primary_term), -1)
            self.terms[0] = self.__primary_term

        # TODO: cleaner and more localized parsing
        self.arguments = {}
        self.special_arguments = {}
        self.arg_list = []
        self.arg_min_count = {}
        self.arg_max_count = {}
        self.keys_by_type = {}
        for a in self.args:
            a = a.strip()
            m = re.match(r'^(\S*?):(\S*)$', a)
            if not m:
                Messager.warning(
                    "Project configuration: Failed to parse argument '%s' (args: %s)" %
                    (a, args), 5)
                raise InvalidProjectConfigException
            key, atypes = m.groups()

            # special case (sorry): if the key is a reserved config
            # string (e.g. "<REL-TYPE>" or "<URL>"), parse differently
            # and store separately
            if key in reserved_config_string:
                if key is self.special_arguments:
                    Messager.warning(
                        "Project configuration: error parsing: %s argument '%s' appears multiple times." %
                        key, 5)
                    raise InvalidProjectConfigException
                # special case in special case: relation type specifications
                # are split by hyphens, nothing else is.
                # (really sorry about this.)
                if key == "<REL-TYPE>":
                    self.special_arguments[key] = atypes.split("-")
                else:
                    self.special_arguments[key] = [atypes]
                # NOTE: skip the rest of processing -- don't add in normal args
                continue

            # Parse "repetition" modifiers. These are regex-like:
            # - Arg      : mandatory argument, exactly one
            # - Arg?     : optional argument, at most one
            # - Arg*     : optional argument, any number
            # - Arg+     : mandatory argument, one or more
            # - Arg{N}   : mandatory, exactly N
            # - Arg{N-M} : mandatory, between N and M

            m = re.match(r'^(\S+?)(\{\S+\}|\?|\*|\+|)$', key)
            if not m:
                Messager.warning(
                    "Project configuration: error parsing argument '%s'." %
                    key, 5)
                raise InvalidProjectConfigException
            key, rep = m.groups()

            if rep == '':
                # exactly one
                minimum_count = 1
                maximum_count = 1
            elif rep == '?':
                # zero or one
                minimum_count = 0
                maximum_count = 1
            elif rep == '*':
                # any number
                minimum_count = 0
                maximum_count = sys.maxsize
            elif rep == '+':
                # one or more
                minimum_count = 1
                maximum_count = sys.maxsize
            else:
                # exact number or range constraint
                assert '{' in rep and '}' in rep, "INTERNAL ERROR"
                m = re.match(r'\{(\d+)(?:-(\d+))?\}$', rep)
                if not m:
                    Messager.warning(
                        "Project configuration: error parsing range '%s' in argument '%s' (syntax is '{MIN-MAX}')." %
                        (rep, key + rep), 5)
                    raise InvalidProjectConfigException
                n1, n2 = m.groups()
                n1 = int(n1)
                if n2 is None:
                    # exact number
                    if n1 == 0:
                        Messager.warning(
                            "Project configuration: cannot have exactly 0 repetitions of argument '%s'." %
                            (key + rep), 5)
                        raise InvalidProjectConfigException
                    minimum_count = n1
                    maximum_count = n1
                else:
                    # range
                    n2 = int(n2)
                    if n1 > n2:
                        Messager.warning(
                            "Project configuration: invalid range %d-%d for argument '%s'." %
                            (n1, n2, key + rep), 5)
                        raise InvalidProjectConfigException
                    minimum_count = n1
                    maximum_count = n2

            # format / config sanity: an argument whose label ends
            # with a digit label cannot be repeated, as this would
            # introduce ambiguity into parsing. (For example, the
            # second "Theme" is "Theme2", and the second "Arg1" would
            # be "Arg12".)
            if maximum_count > 1 and key[-1].isdigit():
                Messager.warning(
                    "Project configuration: error parsing: arguments ending with a digit cannot be repeated: '%s'" %
                    (key + rep), 5)
                raise InvalidProjectConfigException

            if key in self.arguments:
                Messager.warning(
                    "Project configuration: error parsing: %s argument '%s' appears multiple times." %
                    key, 5)
                raise InvalidProjectConfigException

            assert (key not in self.arg_min_count and
                    key not in self.arg_max_count), "INTERNAL ERROR"
            self.arg_min_count[key] = minimum_count
            self.arg_max_count[key] = maximum_count

            self.arg_list.append(key)

            for atype in atypes.split("|"):
                if atype.strip() == "":
                    Messager.warning(
                        "Project configuration: error parsing: empty type for argument '%s'." %
                        a, 5)
                    raise InvalidProjectConfigException

                # Check disabled; need to support arbitrary UTF values
                # for visual.conf. TODO: add this check for other configs.
                # TODO: consider checking for similar for appropriate confs.
#                 if atype not in reserved_config_string and normalize_to_storage_form(atype) != atype:
#                     Messager.warning("Project configuration: '%s' is not a valid argument (should match '^[a-zA-Z0-9_-]*$')" % atype, 5)
#                     raise InvalidProjectConfigException

                if key not in self.arguments:
                    self.arguments[key] = []
                self.arguments[key].append(atype)

                if atype not in self.keys_by_type:
                    self.keys_by_type[atype] = []
                self.keys_by_type[atype].append(key)

    def argument_minimum_count(self, arg):
        """Returns the minimum number of times the given argument is required
        to appear for this type."""
        return self.arg_min_count.get(arg, 0)

    def argument_maximum_count(self, arg):
        """Returns the maximum number of times the given argument is allowed to
        appear for this type."""
        return self.arg_max_count.get(arg, 0)

    def mandatory_arguments(self):
        """Returns the arguments that must appear at least once for this
        type."""
        return [a for a in self.arg_list if self.arg_min_count[a] > 0]

    def multiple_allowed_arguments(self):
        """Returns the arguments that may appear multiple times for this
        type."""
        return [a for a in self.arg_list if self.arg_max_count[a] > 1]

    def storage_form(self):
        """Returns the form of the term used for storage serverside."""
        return self.__primary_term

    def normalizations(self):
        """Returns the normalizations applicable to this node, if any."""
        return self.special_arguments.get('<NORM>', [])


def __require_tab_separator(section):
    """Given a section name, returns True iff in that section of the project
    config only tab separators should be permitted.

    This exception initially introduced to allow slighlty different
    syntax for the [labels] section than others.
    """
    return section == "labels"


def __read_term_hierarchy(input, section=None):
    root_nodes = []
    last_node_at_depth = {}
    last_args_at_depth = {}

    macros = {}
    for l in input:
        # skip empties and lines starting with '#'
        if l.strip() == '' or re.match(r'^\s*#', l):
            continue

        # interpret lines of only hyphens as separators
        # for display
        if re.match(r'^\s*-+\s*$', l):
            # TODO: proper placeholder and placing
            root_nodes.append(SEPARATOR_STR)
            continue

        # interpret lines of the format <STR1>=STR2 as "macro"
        # definitions, defining <STR1> as a placeholder that should be
        # replaced with STR2 whevever it occurs.
        m = re.match(r'^<([a-zA-Z_-]+)>=\s*(.*?)\s*$', l)
        if m:
            name, value = m.groups()
            if name in reserved_config_name:
                Messager.error(
                    "Cannot redefine <%s> in configuration, it is a reserved name." %
                    name)
                # TODO: proper exception
                assert False
            else:
                macros["<%s>" % name] = value
            continue

        # macro expansion
        for n in macros:
            l = l.replace(n, macros[n])

        # check for undefined macros
        for m in re.finditer(r'(<.*?>)', l):
            s = m.group(1)
            assert s in reserved_config_string, "Error: undefined macro %s in configuration. (Note that macros are section-specific.)" % s

        # choose strict tab-only separator or looser any-space
        # separator matching depending on section
        if __require_tab_separator(section):
            m = re.match(r'^(\s*)([^\t]+)(?:\t(.*))?$', l)
        else:
            m = re.match(r'^(\s*)(\S+)(?:\s+(.*))?$', l)
        assert m, "Error parsing line: '%s'" % l
        indent, terms, args = m.groups()
        terms = [t.strip() for t in terms.split("|") if t.strip() != ""]
        if args is None or args.strip() == "":
            args = []
        else:
            args = [a.strip() for a in args.split(",") if a.strip() != ""]

        # older configs allowed space in term strings, splitting those
        # from arguments by space. Trying to parse one of these in the
        # new way will result in a crash from space in arguments.
        # The following is a workaround for the transition.
        if len([x for x in args if re.search('\s', x)]) and '\t' in l:
            # re-parse in the old way (dups from above)
            m = re.match(r'^(\s*)([^\t]+)(?:\t(.*))?$', l)
            assert m, "Error parsing line: '%s'" % l
            indent, terms, args = m.groups()
            terms = [t.strip() for t in terms.split("|") if t.strip() != ""]
            if args is None or args.strip() == "":
                args = []
            else:
                args = [a.strip() for a in args.split(",") if a.strip() != ""]
            # issue a warning
            Messager.warning(
                "Space in term name(s) (%s) on line \"%s\" in config. This feature is deprecated and support will be removed in future versions. Please revise your configuration." %
                (",".join(
                    [
                        '"%s"' %
                        x for x in terms if " " in x]),
                    l),
                20)

        # depth in the ontology corresponds to the number of
        # spaces in the initial indent.
        depth = len(indent)

        # expand <INHERIT> into parent arguments
        expanded_args = []
        for a in args:
            if a != '<INHERIT>':
                expanded_args.append(a)
            else:
                assert depth - 1 in last_args_at_depth, \
                    "Error no parent for '%s'" % l
                expanded_args.extend(last_args_at_depth[depth - 1])
        # TODO: remove, debugging
#         if expanded_args != args:
#             Messager.info('expand: %s --> %s' % (str(args), str(expanded_args)))
        args = expanded_args

        n = TypeHierarchyNode(terms, args)
        if depth == 0:
            # root level, no children assignments
            root_nodes.append(n)
        else:
            # assign as child of last node at the depth of the parent
            assert depth - 1 in last_node_at_depth, \
                "Error: no parent for '%s'" % l
            last_node_at_depth[depth - 1].children.append(n)
        last_node_at_depth[depth] = n
        last_args_at_depth[depth] = args

    return root_nodes


def __read_or_default(filename, default):
    try:
        f = open_textfile(filename, 'r')
        r = f.read()
        f.close()
        return r
    except BaseException:
        # TODO: specific exception handling and reporting
        return default


def __parse_kb_shortcuts(shortcutstr, default, source):
    try:
        shortcuts = {}
        for l in shortcutstr.split("\n"):
            l = l.strip()
            if l == "" or l[:1] == "#":
                continue
            key, type = re.split(r'[ \t]+', l)
            if key in shortcuts:
                Messager.warning(
                    "Project configuration: keyboard shortcut for '%s' defined multiple times. Ignoring all but first ('%s')" %
                    (key, shortcuts[key]))
            else:
                shortcuts[key] = type
    except BaseException:
        # TODO: specific exception handling
        Messager.warning(
            "Project configuration: error parsing keyboard shortcuts from %s. Configuration may be wrong." %
            source, 5)
        shortcuts = default
    return shortcuts


def __parse_access_control(acstr, source):
    try:
        parser = urllib.robotparser.RobotFileParser()
        parser.parse(acstr.split("\n"))
    except BaseException:
        # TODO: specific exception handling
        display_message(
            "Project configuration: error parsing access control rules from %s. Configuration may be wrong." %
            source, "warning", 5)
        parser = None
    return parser


def get_config_path(directory):
    return __read_first_in_directory_tree(
        directory, __annotation_config_filename)[1]


def __read_first_in_directory_tree(directory, filename):
    # config will not be available command-line invocations;
    # in these cases search whole tree
    try:
        from config import BASE_DIR
    except BaseException:
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


def __parse_configs(configstr, source, expected_sections, optional_sections):
    # top-level config structure is a set of term hierarchies
    # separated by lines consisting of "[SECTION]" where SECTION is
    # e.g.  "entities", "relations", etc.

    # start by splitting config file lines by section, also storing
    # the label (default name or alias) used for each section.

    section = "general"
    section_lines = {section: []}
    section_labels = {}
    for ln, l in enumerate(configstr.split("\n")):
        m = re.match(r'^\s*\[(.*)\]\s*$', l)
        if m:
            section = m.group(1)

            # map and store section name/alias (e.g. "spans" -> "entities")
            section_name = SECTION_ALIAS.get(section, section)
            section_labels[section_name] = section
            section = section_name

            if section not in expected_sections:
                Messager.warning(
                    "Project configuration: unexpected section [%s] in %s. Ignoring contents." %
                    (section, source), 5)
            if section not in section_lines:
                section_lines[section] = []
        else:
            section_lines[section].append(l)

    # attempt to parse lines in each section as a term hierarchy
    configs = {}
    for s, sl in list(section_lines.items()):
        try:
            configs[s] = __read_term_hierarchy(sl, s)
        except Exception as e:
            Messager.warning(
                "Project configuration: error parsing section [%s] in %s: %s" %
                (s, source, str(e)), 5)
            raise

    # verify that expected sections are present; replace with empty if not.
    for s in expected_sections:
        if s not in configs:
            if s not in optional_sections:
                Messager.warning(
                    "Project configuration: missing section [%s] in %s. Configuration may be wrong." %
                    (s, source), 5)
            configs[s] = []

    return (configs, section_labels)


def get_configs(
        directory,
        filename,
        defaultstr,
        minconf,
        sections,
        optional_sections):
    if (directory, filename) not in get_configs.__cache:
        configstr, source = __read_first_in_directory_tree(directory, filename)

        if configstr is None:
            # didn't get one; try default dir and fall back to the default
            configstr = __read_or_default(filename, defaultstr)
            if configstr == defaultstr:
                Messager.info(
                    "Project configuration: no configuration file (%s) found, using default." %
                    filename, 5)
                source = "[default]"
            else:
                source = filename

        # try to parse what was found, fall back to minimal config
        try:
            configs, section_labels = __parse_configs(
                configstr, source, sections, optional_sections)
        except BaseException:
            Messager.warning(
                "Project configuration: Falling back to minimal default. Configuration is likely wrong.",
                5)
            configs = minconf
            section_labels = dict([(a, a) for a in sections])

        # very, very special case processing: if we have a type
        # "Equiv" defined in a "relations" section that doesn't
        # specify a "<REL-TYPE>", automatically fill "symmetric" and
        # "transitive". This is to support older configurations that
        # rely on the type "Equiv" to identify the relation as an
        # equivalence.
        if 'relations' in configs:
            for r in configs['relations']:
                if r == SEPARATOR_STR:
                    continue
                if (r.storage_form() == "Equiv" and
                        "<REL-TYPE>" not in r.special_arguments):
                    # this was way too much noise; will only add in after
                    # at least most configs are revised.
                    #                     Messager.warning('Note: "Equiv" defined in config without "<REL-TYPE>"; assuming symmetric and transitive. Consider revising config to add "<REL-TYPE>:symmetric-transitive" to definition.')
                    r.special_arguments["<REL-TYPE>"] = ["symmetric",
                                                         "transitive"]

        get_configs.__cache[(directory, filename)] = (configs, section_labels)

    return get_configs.__cache[(directory, filename)]


get_configs.__cache = {}


def __get_access_control(directory, filename, default_rules):

    acstr, source = __read_first_in_directory_tree(directory, filename)

    if acstr is None:
        acstr = default_rules  # TODO read or default isntead of default
        if acstr == default_rules:
            source = "[default rules]"
        else:
            source = filename
    ac_oracle = __parse_access_control(acstr, source)
    return ac_oracle


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


# final fallback for configuration; a minimal known-good config
__minimal_configuration = {
    ENTITY_SECTION: [
        TypeHierarchyNode(
            ["Protein"])], RELATION_SECTION: [
                TypeHierarchyNode(
                    ["Equiv"], [
                        "Arg1:Protein", "Arg2:Protein", "<REL-TYPE>:symmetric-transitive"])], EVENT_SECTION: [
                            TypeHierarchyNode(
                                ["Event"], ["Theme:Protein"])], ATTRIBUTE_SECTION: [
                                    TypeHierarchyNode(
                                        ["Negation"], ["Arg:<EVENT>"])], }


def get_annotation_configs(directory):
    return get_configs(directory,
                       __annotation_config_filename,
                       __default_configuration,
                       __minimal_configuration,
                       __expected_annotation_sections,
                       __optional_annotation_sections)


# final fallback for visual configuration; minimal known-good config
__minimal_visual = {
    LABEL_SECTION: [TypeHierarchyNode(["Protein", "Pro", "P"]),
                    TypeHierarchyNode(["Equiv", "Eq"]),
                    TypeHierarchyNode(["Event", "Ev"])],
    DRAWING_SECTION: [TypeHierarchyNode([VISUAL_SPAN_DEFAULT], ["fgColor:black", "bgColor:white"]),
                      TypeHierarchyNode([VISUAL_ARC_DEFAULT], ["color:black"]),
                      TypeHierarchyNode([VISUAL_ATTR_DEFAULT], ["glyph:*"])],
}


def get_visual_configs(directory):
    return get_configs(directory,
                       __visual_config_filename,
                       __default_visual,
                       __minimal_visual,
                       __expected_visual_sections,
                       __optional_visual_sections)


# final fallback for tools configuration; minimal known-good config
__minimal_tools = {
    OPTIONS_SECTION: [],
    SEARCH_SECTION: [
        TypeHierarchyNode(
            ["google"],
            ["<URL>:http://www.google.com/search?q=%s"])],
    ANNOTATORS_SECTION: [],
    DISAMBIGUATORS_SECTION: [],
    NORMALIZATION_SECTION: [],
}


def get_tools_configs(directory):
    return get_configs(directory,
                       __tools_config_filename,
                       __default_tools,
                       __minimal_tools,
                       __expected_tools_sections,
                       __optional_tools_sections)


def get_entity_type_hierarchy(directory):
    return get_annotation_configs(directory)[0][ENTITY_SECTION]


def get_relation_type_hierarchy(directory):
    return get_annotation_configs(directory)[0][RELATION_SECTION]


def get_event_type_hierarchy(directory):
    return get_annotation_configs(directory)[0][EVENT_SECTION]


def get_attribute_type_hierarchy(directory):
    return get_annotation_configs(directory)[0][ATTRIBUTE_SECTION]


def get_annotation_config_section_labels(directory):
    return get_annotation_configs(directory)[1]

# TODO: too much caching?


def get_labels(directory):
    cache = get_labels.__cache
    if directory not in cache:
        l = {}
        for t in get_visual_configs(directory)[0][LABEL_SECTION]:
            if t.storage_form() in l:
                Messager.warning(
                    "In configuration, labels for '%s' defined more than once. Only using the last set." %
                    t.storage_form(), -1)
            # first is storage for, rest are labels.
            l[t.storage_form()] = t.terms[1:]
        cache[directory] = l
    return cache[directory]


get_labels.__cache = {}

# TODO: too much caching?


def get_drawing_types(directory):
    cache = get_drawing_types.__cache
    if directory not in cache:
        l = set()
        for n in get_drawing_config(directory):
            l.add(n.storage_form())
        cache[directory] = list(l)
    return cache[directory]


get_drawing_types.__cache = {}


def get_option_config(directory):
    return get_tools_configs(directory)[0][OPTIONS_SECTION]


def get_drawing_config(directory):
    return get_visual_configs(directory)[0][DRAWING_SECTION]


def get_visual_option_config(directory):
    return get_visual_configs(directory)[0][OPTIONS_SECTION]


def get_visual_config_section_labels(directory):
    return get_visual_configs(directory)[1]


def get_search_config(directory):
    return get_tools_configs(directory)[0][SEARCH_SECTION]


def get_annotator_config(directory):
    return get_tools_configs(directory)[0][ANNOTATORS_SECTION]


def get_disambiguator_config(directory):
    return get_tools_configs(directory)[0][DISAMBIGUATORS_SECTION]


def get_normalization_config(directory):
    return get_tools_configs(directory)[0][NORMALIZATION_SECTION]


def get_tools_config_section_labels(directory):
    return get_tools_configs(directory)[1]


def get_access_control(directory):
    cache = get_access_control.__cache
    if directory not in cache:
        a = __get_access_control(directory,
                                 __access_control_filename,
                                 __default_access_control)
        cache[directory] = a

    return cache[directory]


get_access_control.__cache = {}


def get_kb_shortcuts(directory):
    cache = get_kb_shortcuts.__cache
    if directory not in cache:
        a = __get_kb_shortcuts(directory,
                               __kb_shortcut_filename,
                               __default_kb_shortcuts,
                               {"P": "Positive_regulation"})
        cache[directory] = a

    return cache[directory]


get_kb_shortcuts.__cache = {}


def __collect_type_list(node, collected):
    if node == SEPARATOR_STR:
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

# TODO: it's not clear it makes sense for all of these methods to have
# their own caches; this seems a bit like a case of premature
# optimization to me. Consider simplifying.


def get_entity_type_list(directory):
    cache = get_entity_type_list.__cache
    if directory not in cache:
        cache[directory] = __type_hierarchy_to_list(
            get_entity_type_hierarchy(directory))
    return cache[directory]


get_entity_type_list.__cache = {}


def get_event_type_list(directory):
    cache = get_event_type_list.__cache
    if directory not in cache:
        cache[directory] = __type_hierarchy_to_list(
            get_event_type_hierarchy(directory))
    return cache[directory]


get_event_type_list.__cache = {}


def get_relation_type_list(directory):
    cache = get_relation_type_list.__cache
    if directory not in cache:
        cache[directory] = __type_hierarchy_to_list(
            get_relation_type_hierarchy(directory))
    return cache[directory]


get_relation_type_list.__cache = {}


def get_attribute_type_list(directory):
    cache = get_attribute_type_list.__cache
    if directory not in cache:
        cache[directory] = __type_hierarchy_to_list(
            get_attribute_type_hierarchy(directory))
    return cache[directory]


get_attribute_type_list.__cache = {}


def get_search_config_list(directory):
    cache = get_search_config_list.__cache
    if directory not in cache:
        cache[directory] = __type_hierarchy_to_list(
            get_search_config(directory))
    return cache[directory]


get_search_config_list.__cache = {}


def get_annotator_config_list(directory):
    cache = get_annotator_config_list.__cache
    if directory not in cache:
        cache[directory] = __type_hierarchy_to_list(
            get_annotator_config(directory))
    return cache[directory]


get_annotator_config_list.__cache = {}


def get_disambiguator_config_list(directory):
    cache = get_disambiguator_config_list.__cache
    if directory not in cache:
        cache[directory] = __type_hierarchy_to_list(
            get_disambiguator_config(directory))
    return cache[directory]


get_disambiguator_config_list.__cache = {}


def get_normalization_config_list(directory):
    cache = get_normalization_config_list.__cache
    if directory not in cache:
        cache[directory] = __type_hierarchy_to_list(
            get_normalization_config(directory))
    return cache[directory]


get_normalization_config_list.__cache = {}


def get_node_by_storage_form(directory, term):
    cache = get_node_by_storage_form.__cache
    if directory not in cache:
        d = {}
        for e in get_entity_type_list(
                directory) + get_event_type_list(directory):
            t = e.storage_form()
            if t in d:
                Messager.warning(
                    "Project configuration: term %s appears multiple times, only using last. Configuration may be wrong." %
                    t, 5)
            d[t] = e
        cache[directory] = d

    return cache[directory].get(term, None)


get_node_by_storage_form.__cache = {}


def _get_option_by_storage_form(directory, term, config, cache):
    if directory not in cache:
        d = {}
        for n in config:
            t = n.storage_form()
            if t in d:
                Messager.warning(
                    "Project configuration: %s appears multiple times, only using last. Configuration may be wrong." %
                    t, 5)
            d[t] = {}
            for a in n.arguments:
                if len(n.arguments[a]) != 1:
                    Messager.warning(
                        "Project configuration: %s key %s has multiple values, only using first. Configuration may be wrong." %
                        (t, a), 5)
                d[t][a] = n.arguments[a][0]

        cache[directory] = d

    return cache[directory].get(term, None)


def get_option_config_by_storage_form(directory, term):
    cache = get_option_config_by_storage_form.__cache
    config = get_option_config(directory)
    return _get_option_by_storage_form(directory, term, config, cache)


get_option_config_by_storage_form.__cache = {}


def get_visual_option_config_by_storage_form(directory, term):
    cache = get_visual_option_config_by_storage_form.__cache
    config = get_visual_option_config(directory)
    return _get_option_by_storage_form(directory, term, config, cache)


get_visual_option_config_by_storage_form.__cache = {}

# access for settings for specific options in tools.conf
# TODO: avoid fixed string values here, define vars earlier


def options_get_validation(directory):
    v = get_option_config_by_storage_form(directory, 'Validation')
    return 'none' if v is None else v.get('validate', 'none')


def options_get_tokenization(directory):
    v = get_option_config_by_storage_form(directory, 'Tokens')
    return 'whitespace' if v is None else v.get('tokenizer', 'whitespace')


def options_get_ssplitter(directory):
    v = get_option_config_by_storage_form(directory, 'Sentences')
    return 'regex' if v is None else v.get('splitter', 'regex')


def options_get_annlogfile(directory):
    v = get_option_config_by_storage_form(directory, 'Annotation-log')
    return '<NONE>' if v is None else v.get('logfile', '<NONE>')

# access for settings for specific options in visual.conf


def visual_options_get_arc_bundle(directory):
    v = get_visual_option_config_by_storage_form(directory, 'Arcs')
    return 'none' if v is None else v.get('bundle', 'none')


def visual_options_get_text_direction(directory):
    v = get_visual_option_config_by_storage_form(directory, 'Text')
    return 'ltr' if v is None else v.get('direction', 'ltr')


def get_drawing_config_by_storage_form(directory, term):
    cache = get_drawing_config_by_storage_form.__cache
    if directory not in cache:
        d = {}
        for n in get_drawing_config(directory):
            t = n.storage_form()
            if t in d:
                Messager.warning(
                    "Project configuration: term %s appears multiple times, only using last. Configuration may be wrong." %
                    t, 5)
            d[t] = {}
            for a in n.arguments:
                # attribute drawing can be specified with multiple
                # values (multi-valued attributes), other parts of
                # drawing config should have single values only.
                if len(n.arguments[a]) != 1:
                    if a in ATTR_DRAWING_ATTRIBUTES:
                        # use multi-valued directly
                        d[t][a] = n.arguments[a]
                    else:
                        # warn and pass
                        Messager.warning(
                            "Project configuration: expected single value for %s argument %s, got '%s'. Configuration may be wrong." %
                            (t, a, "|".join(
                                n.arguments[a])))
                else:
                    d[t][a] = n.arguments[a][0]

        # TODO: hack to get around inability to have commas in values;
        # fix original issue instead
        for t in d:
            for k in d[t]:
                # sorry about this
                if not isinstance(d[t][k], list):
                    d[t][k] = d[t][k].replace("-", ",")
                else:
                    for i in range(len(d[t][k])):
                        d[t][k][i] = d[t][k][i].replace("-", ",")

        default_keys = [VISUAL_SPAN_DEFAULT,
                        VISUAL_ARC_DEFAULT,
                        VISUAL_ATTR_DEFAULT]
        for default_dict in [d.get(dk, {}) for dk in default_keys]:
            for k in default_dict:
                for t in d:
                    d[t][k] = d[t].get(k, default_dict[k])

        # Kind of a special case: recognize <NONE> as "deleting" an
        # attribute (prevents default propagation) and <EMPTY> as
        # specifying that a value should be the empty string
        # (can't be written as such directly).
        for t in d:
            todelete = [k for k in d[t] if d[t][k] == '<NONE>']
            for k in todelete:
                del d[t][k]

            for k in d[t]:
                if d[t][k] == '<EMPTY>':
                    d[t][k] = ''

        cache[directory] = d

    return cache[directory].get(term, None)


get_drawing_config_by_storage_form.__cache = {}


def __directory_relations_by_arg_num(
        directory, num, atype, include_special=False):
    assert num >= 0 and num < 2, "INTERNAL ERROR"

    rels = []

    entity_types = set([t.storage_form()
                        for t in get_entity_type_list(directory)])
    event_types = set([t.storage_form()
                       for t in get_event_type_list(directory)])

    for r in get_relation_type_list(directory):
        # "Special" nesting relations ignored unless specifically
        # requested
        if r.storage_form() in SPECIAL_RELATION_TYPES and not include_special:
            continue

        if len(r.arg_list) != 2:
            # Don't complain about argument constraints for unused relations
            if not r.unused:
                Messager.warning(
                    "Relation type %s has %d arguments in configuration (%s; expected 2). Please fix configuration." %
                    (r.storage_form(), len(
                        r.arg_list), ",".join(
                        r.arg_list)))
        else:
            types = r.arguments[r.arg_list[num]]
            for type_ in types:
                # TODO: there has to be a better way
                if (type_ == atype or
                    type_ == "<ANY>" or
                    atype == "<ANY>" or
                    (type_ in entity_types and atype == "<ENTITY>") or
                    (type_ in event_types and atype == "<EVENT>") or
                    (atype in entity_types and type_ == "<ENTITY>") or
                        (atype in event_types and type_ == "<EVENT>")):
                    rels.append(r)
                    # TODO: why not break here?

    return rels


def get_relations_by_arg1(directory, atype, include_special=False):
    cache = get_relations_by_arg1.__cache
    cache[directory] = cache.get(directory, {})
    if (atype, include_special) not in cache[directory]:
        cache[directory][(atype, include_special)] = __directory_relations_by_arg_num(
            directory, 0, atype, include_special)
    return cache[directory][(atype, include_special)]


get_relations_by_arg1.__cache = {}


def get_relations_by_arg2(directory, atype, include_special=False):
    cache = get_relations_by_arg2.__cache
    cache[directory] = cache.get(directory, {})
    if (atype, include_special) not in cache[directory]:
        cache[directory][(atype, include_special)] = __directory_relations_by_arg_num(
            directory, 1, atype, include_special)
    return cache[directory][(atype, include_special)]


get_relations_by_arg2.__cache = {}


def get_relations_by_storage_form(directory, rtype, include_special=False):
    cache = get_relations_by_storage_form.__cache
    cache[directory] = cache.get(directory, {})
    if include_special not in cache[directory]:
        cache[directory][include_special] = {}
        for r in get_relation_type_list(directory):
            if (r.storage_form() in SPECIAL_RELATION_TYPES and
                    not include_special):
                continue
            if r.unused:
                continue
            if r.storage_form() not in cache[directory][include_special]:
                cache[directory][include_special][r.storage_form()] = []
            cache[directory][include_special][r.storage_form()].append(r)
    return cache[directory][include_special].get(rtype, [])


get_relations_by_storage_form.__cache = {}


def get_labels_by_storage_form(directory, term):
    cache = get_labels_by_storage_form.__cache
    if directory not in cache:
        cache[directory] = {}
        for l, labels in list(get_labels(directory).items()):
            # recognize <EMPTY> as specifying that a label should
            # be the empty string
            labels = [lab if lab != '<EMPTY>' else ' ' for lab in labels]
            cache[directory][l] = labels
    return cache[directory].get(term, None)


get_labels_by_storage_form.__cache = {}

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
    'Tissue',
    # 'Not_sure',
    # 'Other',
    'Other_pharmaceutical_agent',
]

# helper; doesn't really belong here
# TODO: shouldn't we have an utils.py or something for stuff like this?


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
        # debugging (note: latter test for windows paths)
        if directory[:1] != "/" and not re.search(r'^[a-zA-Z]:\\', directory):
            Messager.debug(
                "Project config received relative directory ('%s'), configuration may not be found." %
                directory, duration=-1)
        self.directory = directory

    def mandatory_arguments(self, atype):
        """Returns the mandatory argument types that must be present for an
        annotation of the given type."""
        node = get_node_by_storage_form(self.directory, atype)
        if node is None:
            Messager.warning(
                "Project configuration: unknown event type %s. Configuration may be wrong." %
                atype)
            return []
        return node.mandatory_arguments()

    def multiple_allowed_arguments(self, atype):
        """Returns the argument types that are allowed to be filled more than
        once for an annotation of the given type."""
        node = get_node_by_storage_form(self.directory, atype)
        if node is None:
            Messager.warning(
                "Project configuration: unknown event type %s. Configuration may be wrong." %
                atype)
            return []
        return node.multiple_allowed_arguments()

    def argument_maximum_count(self, atype, arg):
        """Returns the maximum number of times that the given argument is
        allowed to be filled for an annotation of the given type."""
        node = get_node_by_storage_form(self.directory, atype)
        if node is None:
            Messager.warning(
                "Project configuration: unknown event type %s. Configuration may be wrong." %
                atype)
            return 0
        return node.argument_maximum_count(arg)

    def argument_minimum_count(self, atype, arg):
        """Returns the minimum number of times that the given argument is
        allowed to be filled for an annotation of the given type."""
        node = get_node_by_storage_form(self.directory, atype)
        if node is None:
            Messager.warning(
                "Project configuration: unknown event type %s. Configuration may be wrong." %
                atype)
            return 0
        return node.argument_minimum_count(arg)

    def arc_types_from(self, from_ann):
        return self.arc_types_from_to(from_ann)

    def relation_types_from(self, from_ann, include_special=False):
        """Returns the possible relation types that can have an annotation of
        the given type as their arg1."""
        return [r.storage_form() for r in get_relations_by_arg1(
            self.directory, from_ann, include_special)]

    def relation_types_to(self, to_ann, include_special=False):
        """Returns the possible relation types that can have an annotation of
        the given type as their arg2."""
        return [
            r.storage_form() for r in get_relations_by_arg2(
                self.directory,
                to_ann,
                include_special)]

    def relation_types_from_to(self, from_ann, to_ann, include_special=False):
        """Returns the possible relation types that can have the given arg1 and
        arg2."""
        types = []

        t1r = get_relations_by_arg1(self.directory, from_ann, include_special)
        t2r = get_relations_by_arg2(self.directory, to_ann, include_special)

        for r in t1r:
            if r in t2r:
                types.append(r.storage_form())

        return types

    def overlap_types(self, inner, outer):
        """Returns the set of annotation overlap types that have been
        configured for the given pair of annotations."""
        # TODO: this is O(NM) for relation counts N and M and goes
        # past much of the implemented caching. Might become a
        # bottleneck for annotations with large type systems.
        t1r = get_relations_by_arg1(self.directory, inner, True)
        t2r = get_relations_by_arg2(self.directory, outer, True)

        types = []
        for r in (s for s in t1r if s.storage_form()
                  in SPECIAL_RELATION_TYPES):
            if r in t2r:
                types.append(r)

        # new-style overlap configuration ("<OVERLAP>") takes precedence
        # over old-style configuration ("ENTITY-NESTING").
        ovl_types = set()

        ovl = [r for r in types if r.storage_form() == TEXTBOUND_OVERLAP_TYPE]
        nst = [r for r in types if r.storage_form() == ENTITY_NESTING_TYPE]

        if ovl:
            if nst:
                Messager.warning(
                    'Warning: both ' +
                    TEXTBOUND_OVERLAP_TYPE +
                    ' and ' +
                    ENTITY_NESTING_TYPE +
                    ' defined for ' +
                    '(' +
                    inner +
                    ',' +
                    outer +
                    ') in config. ' +
                    'Ignoring latter.')
            for r in ovl:
                if OVERLAP_TYPE_ARG not in r.special_arguments:
                    Messager.warning('Warning: missing ' + OVERLAP_TYPE_ARG +
                                     ' for ' + TEXTBOUND_OVERLAP_TYPE +
                                     ', ignoring specification.')
                    continue
                for val in r.special_arguments[OVERLAP_TYPE_ARG]:
                    ovl_types |= set(val.split('|'))
        elif nst:
            # translate into new-style configuration
            ovl_types = set(['contain'])
        else:
            ovl_types = set()

        undefined_types = [t for t in ovl_types if
                           t not in ('contain', 'equal', 'cross', '<ANY>')]
        if undefined_types:
            Messager.warning('Undefined ' + OVERLAP_TYPE_ARG + ' value(s) ' +
                             str(undefined_types) + ' for ' +
                             '(' + inner + ',' + outer + ') in config. ')
        return ovl_types

    def span_can_contain(self, inner, outer):
        """Returns True if the configuration allows the span of an annotation
        of type inner to (properly) contain an annotation of type outer, False
        otherwise."""
        ovl_types = self.overlap_types(inner, outer)
        if 'contain' in ovl_types or '<ANY>' in ovl_types:
            return True
        ovl_types = self.overlap_types(outer, inner)
        if '<ANY>' in ovl_types:
            return True
        return False

    def spans_can_be_equal(self, t1, t2):
        """Returns True if the configuration allows the spans of annotations of
        type t1 and t2 to be equal, False otherwise."""
        ovl_types = self.overlap_types(t1, t2)
        if 'equal' in ovl_types or '<ANY>' in ovl_types:
            return True
        ovl_types = self.overlap_types(t2, t1)
        if 'equal' in ovl_types or '<ANY>' in ovl_types:
            return True
        return False

    def spans_can_cross(self, t1, t2):
        """Returns True if the configuration allows the spans of annotations of
        type t1 and t2 to cross, False otherwise."""
        ovl_types = self.overlap_types(t1, t2)
        if 'cross' in ovl_types or '<ANY>' in ovl_types:
            return True
        ovl_types = self.overlap_types(t2, t1)
        if 'cross' in ovl_types or '<ANY>' in ovl_types:
            return True
        return False

    def all_connections(self, include_special=False):
        """Returns a dict of dicts of lists, outer dict keyed by entity/event
        type, inner dicts by role/relation type, and lists containing
        entity/event types, representing all possible connections between
        annotations.

        This function is provided to optimize access to the entire
        annotation configuration for passing it to the client and should
        never be used to check for individual connections. The caller
        must not change the contents of the returned collection.
        """

        # TODO: are these uniques really necessary?
        entity_types = unique_preserve_order(self.get_entity_types())
        event_types = unique_preserve_order(self.get_event_types())
        all_types = unique_preserve_order(entity_types + event_types)

        connections = {}

        # TODO: it might be possible to avoid copies like
        # entity_types[:] and all_types[:] here. Consider the
        # possibility.

        for t1 in all_types:
            assert t1 not in connections, "INTERNAL ERROR"
            connections[t1] = {}

            processed_as_relation = {}

            # relations

            rels = get_relations_by_arg1(self.directory, t1, include_special)

            for r in rels:
                a = r.storage_form()

                conns = connections[t1].get(a, [])

                # magic number "1" is for 2nd argument
                args = r.arguments[r.arg_list[1]]

                if "<ANY>" in args:
                    connections[t1][a] = all_types[:]
                else:
                    for t2 in args:
                        if t2 == "<ENTITY>":
                            conns.extend(entity_types)
                        elif t2 == "<EVENT>":
                            conns.extend(event_types)
                        else:
                            conns.append(t2)
                    connections[t1][a] = unique_preserve_order(conns)

                processed_as_relation[a] = True

            # event arguments

            n1 = get_node_by_storage_form(self.directory, t1)

            for a, args in list(n1.arguments.items()):
                if a in processed_as_relation:
                    Messager.warning(
                        "Project configuration: %s appears both as role and relation. Configuration may be wrong." %
                        a)
                    # won't try to resolve
                    continue

                assert a not in connections[t1], "INTERNAL ERROR"

                # TODO: dedup w/above
                if "<ANY>" in args:
                    connections[t1][a] = all_types[:]
                else:
                    conns = []
                    for t2 in args:
                        if t2 == "<EVENT>":
                            conns.extend(event_types)
                        elif t2 == "<ENTITY>":
                            conns.extend(entity_types)
                        else:
                            conns.append(t2)
                    connections[t1][a] = unique_preserve_order(conns)

        return connections

    def arc_types_from_to(
            self,
            from_ann,
            to_ann="<ANY>",
            include_special=False):
        """Returns the possible arc types that can connect an annotation of
        type from_ann to an annotation of type to_ann.

        If to_ann has the value \"<ANY>\", returns all possible arc
        types.
        """

        from_node = get_node_by_storage_form(self.directory, from_ann)

        if from_node is None:
            Messager.warning(
                "Project configuration: unknown textbound/event type %s. Configuration may be wrong." %
                from_ann)
            return []

        if to_ann == "<ANY>":
            relations_from = get_relations_by_arg1(
                self.directory, from_ann, include_special)
            # TODO: consider using from_node.arg_list instead of .arguments for
            # order
            return unique_preserve_order(
                [role for role in from_node.arguments] + [r.storage_form() for r in relations_from])

        # specific hits
        types = from_node.keys_by_type.get(to_ann, [])

        if "<ANY>" in from_node.keys_by_type:
            types += from_node.keys_by_type["<ANY>"]

        # generic arguments
        if self.is_event_type(to_ann) and '<EVENT>' in from_node.keys_by_type:
            types += from_node.keys_by_type['<EVENT>']
        if self.is_physical_entity_type(
                to_ann) and '<ENTITY>' in from_node.keys_by_type:
            types += from_node.keys_by_type['<ENTITY>']

        # relations
        types.extend(self.relation_types_from_to(from_ann, to_ann))

        return unique_preserve_order(types)

    def attributes_for(self, ann_type):
        """Returs a list of the possible attribute types for an annotation of
        the given type."""
        attrs = []
        for attr in get_attribute_type_list(self.directory):
            if attr == SEPARATOR_STR:
                continue

            if 'Arg' not in attr.arguments:
                Messager.warning(
                    "Project configuration: config error: attribute '%s' lacks 'Arg:' specification." %
                    attr.storage_form())
                continue

            types = attr.arguments['Arg']

            if ((ann_type in types) or ('<ANY>' in types) or
                (self.is_event_type(ann_type) and '<EVENT>' in types) or
                (self.is_physical_entity_type(ann_type) and '<ENTITY>' in types)
                or
                    (self.is_relation_type(ann_type) and '<RELATION>' in types)):
                attrs.append(attr.storage_form())

        return attrs

    def get_labels(self):
        return get_labels(self.directory)

    def get_kb_shortcuts(self):
        return get_kb_shortcuts(self.directory)

    def get_access_control(self):
        return get_access_control(self.directory)

    def get_attribute_types(self):
        return [t.storage_form()
                for t in get_attribute_type_list(self.directory)]

    def get_event_types(self):
        return [t.storage_form() for t in get_event_type_list(self.directory)]

    def get_relation_types(self):
        return [t.storage_form()
                for t in get_relation_type_list(self.directory)]

    def get_equiv_types(self):
        # equivalence relations are those relations that are symmetric
        # and transitive, i.e. that have "symmetric" and "transitive"
        # in their "<REL-TYPE>" special argument values.
        return [t.storage_form() for t in get_relation_type_list(self.directory)
                if "<REL-TYPE>" in t.special_arguments and
                "symmetric" in t.special_arguments["<REL-TYPE>"] and
                "transitive" in t.special_arguments["<REL-TYPE>"]]

    def get_relations_by_type(self, _type):
        return get_relations_by_storage_form(self.directory, _type)

    def get_labels_by_type(self, _type):
        return get_labels_by_storage_form(self.directory, _type)

    def get_drawing_types(self):
        return get_drawing_types(self.directory)

    def get_drawing_config_by_type(self, _type):
        return get_drawing_config_by_storage_form(self.directory, _type)

    def get_search_config(self):
        search_config = []
        for r in get_search_config_list(self.directory):
            if '<URL>' not in r.special_arguments:
                Messager.warning(
                    'Project configuration: config error: missing <URL> specification for %s search.' %
                    r.storage_form())
            else:
                search_config.append(
                    (r.storage_form(), r.special_arguments['<URL>'][0]))
        return search_config

    def _get_tool_config(self, tool_list):
        tool_config = []
        for r in tool_list:
            if '<URL>' not in r.special_arguments:
                Messager.warning(
                    'Project configuration: config error: missing <URL> specification for %s.' %
                    r.storage_form())
                continue
            if 'tool' not in r.arguments:
                Messager.warning(
                    'Project configuration: config error: missing tool name ("tool") for %s.' %
                    r.storage_form())
                continue
            if 'model' not in r.arguments:
                Messager.warning(
                    'Project configuration: config error: missing model name ("model") for %s.' %
                    r.storage_form())
                continue
            tool_config.append((r.storage_form(),
                                r.arguments['tool'][0],
                                r.arguments['model'][0],
                                r.special_arguments['<URL>'][0]))
        return tool_config

    def get_disambiguator_config(self):
        tool_list = get_disambiguator_config_list(self.directory)
        return self._get_tool_config(tool_list)

    def get_annotator_config(self):
        # TODO: "annotator" is a very confusing term for a web service
        # that does automatic annotation in the context of a tool
        # where most annotators are expected to be human. Rethink.
        tool_list = get_annotator_config_list(self.directory)
        return self._get_tool_config(tool_list)

    def get_normalization_config(self):
        norm_list = get_normalization_config_list(self.directory)
        norm_config = []
        for n in norm_list:
            if 'DB' not in n.arguments:
                # optional, server looks in default location if None
                n.arguments['DB'] = [None]
            if '<URL>' not in n.special_arguments:
                Messager.warning(
                    'Project configuration: config error: missing <URL> specification for %s.' %
                    n.storage_form())
                continue
            if '<URLBASE>' not in n.special_arguments:
                # now optional, client skips link generation if None
                n.special_arguments['<URLBASE>'] = [None]
            norm_config.append((n.storage_form(),
                                n.special_arguments['<URL>'][0],
                                n.special_arguments['<URLBASE>'][0],
                                n.arguments['DB'][0]))
        return norm_config

    def get_entity_types(self):
        return [t.storage_form() for t in get_entity_type_list(self.directory)]

    def get_entity_type_hierarchy(self):
        return get_entity_type_hierarchy(self.directory)

    def get_relation_type_hierarchy(self):
        return get_relation_type_hierarchy(self.directory)

    def get_event_type_hierarchy(self):
        return get_event_type_hierarchy(self.directory)

    def get_attribute_type_hierarchy(self):
        return get_attribute_type_hierarchy(self.directory)

    def _get_filtered_attribute_type_hierarchy(self, types):
        from copy import deepcopy
        # TODO: This doesn't property implement recursive traversal
        # and filtering, instead only checking the topmost nodes.
        filtered = []
        for t in self.get_attribute_type_hierarchy():
            if t.storage_form() in types:
                filtered.append(deepcopy(t))
        return filtered

    def attributes_for_types(self, types):
        """Returns list containing the attribute types that are applicable to
        at least one of the given annotation types."""
        # list to preserve order, dict for lookup
        attribute_list = []
        seen = {}
        for t in types:
            for a in self.attributes_for(t):
                if a not in seen:
                    attribute_list.append(a)
                    seen[a] = True
        return attribute_list

    def get_entity_attribute_type_hierarchy(self):
        """Returns the attribute type hierarchy filtered to include only
        attributes that apply to at least one entity."""
        attr_types = self.attributes_for_types(self.get_entity_types())
        return self._get_filtered_attribute_type_hierarchy(attr_types)

    def get_relation_attribute_type_hierarchy(self):
        """Returns the attribute type hierarchy filtered to include only
        attributes that apply to at least one relation."""
        attr_types = self.attributes_for_types(self.get_relation_types())
        return self._get_filtered_attribute_type_hierarchy(attr_types)

    def get_event_attribute_type_hierarchy(self):
        """Returns the attribute type hierarchy filtered to include only
        attributes that apply to at least one event."""
        attr_types = self.attributes_for_types(self.get_event_types())
        return self._get_filtered_attribute_type_hierarchy(attr_types)

    def preferred_display_form(self, t):
        """Given a storage form label, returns the preferred display form as
        defined by the label configuration (labels.conf)"""
        labels = get_labels_by_storage_form(self.directory, t)
        if labels is None or len(labels) < 1:
            return t
        else:
            return labels[0]

    def is_physical_entity_type(self, t):
        if t in self.get_entity_types() or t in self.get_event_types():
            return t in self.get_entity_types()
        # TODO: remove this temporary hack
        if t in very_likely_physical_entity_types:
            return True
        return t in self.get_entity_types()

    def is_event_type(self, t):
        return t in self.get_event_types()

    def is_relation_type(self, t):
        return t in self.get_relation_types()

    def is_equiv_type(self, t):
        return t in self.get_equiv_types()

    def is_configured_type(self, t):
        return (t in self.get_entity_types() or
                t in self.get_event_types() or
                t in self.get_relation_types())

    def type_category(self, t):
        """Returns the category of the given type t.

        The categories can be compared for equivalence but offer no
        other interface.
        """
        if self.is_physical_entity_type(t):
            return ENTITY_CATEGORY
        elif self.is_event_type(t):
            return EVENT_CATEGORY
        elif self.is_relation_type(t):
            return RELATION_CATEGORY
        else:
            # TODO: others
            return UNKNOWN_CATEGORY
