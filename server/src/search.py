#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

# Search-related functionality for BioNLP Shared Task - style
# annotations.

from __future__ import with_statement

import re
import annotation

from message import Messager

class SearchMatchSet(object):
    """
    Represents a set of matches to a search. Each match is represented
    as an (ann_obj, ann) pair, where ann_obj is an Annotations object
    an ann an Annotation belonging to the corresponding ann_obj.
    """

    def __init__(self, criterion, matches=[]):
        self.criterion = criterion
        self.__matches = matches

    def add_match(self, ann_obj, ann):
        self.__matches.append((ann_obj, ann))

    # TODO: would be better with an iterator
    def get_matches(self):
        return self.__matches

    def __len__(self):
        return len(self.__matches)

class TextMatch(object):
    """
    Represents a text span matching a query.
    """
    def __init__(self, start, end, text):
        self.start = start
        self.end = end
        self.text = text
        # TODO: temporary "fake ID" to make other bits of code happy, remove
        # once no longer necessary
        self.id = ""

    def get_text(self):
        return self.text

    def __str__(self):
        # Format like textbound, but w/o ID or type
        return u'%d %d\t%s' % (self.start, self.end, self.text)

def __filenames_to_annotations(filenames):
    """
    Given file names, returns corresponding Annotations objects.
    """
    
    # TODO: error output should be done via messager to allow
    # both command-line and GUI invocations

    anns = []
    for fn in filenames:
        try:
            # remove suffixes for Annotations to prompt parsing of .a1
            # also.
            nosuff_fn = fn.replace(".ann","").replace(".a2","").replace(".rel","")
            ann_obj = annotation.TextAnnotations(nosuff_fn, read_only=True)
            anns.append(ann_obj)
        except annotation.AnnotationFileNotFoundError:
            print >> sys.stderr, "%s:\tFailed: file not found" % fn
        except annotation.AnnotationNotFoundError, e:
            print >> sys.stderr, "%s:\tFailed: %s" % (fn, e)

    if len(anns) != len(filenames):
        print >> sys.stderr, "Note: only checking %d/%d given files" % (len(anns), len(filenames))

    return anns

def __directory_to_annotations(directory):
    """
    Given a directory, returns Annotations objects for contained files.
    """
    # TODO: put this shared functionality in a more reasonable place
    from document import real_directory,_listdir
    from os.path import join as path_join

    real_dir = real_directory(directory)
    # Get the document names
    base_names = [fn[0:-4] for fn in _listdir(real_dir) if fn.endswith('txt')]

    filenames = [path_join(real_dir, bn) for bn in base_names]

    return __filenames_to_annotations(filenames)

def eq_text_neq_type_spans(ann_objs, restrict_types=[], ignore_types=[]):
    """
    Searches for annotated spans that match in string content but
    disagree in type in given Annotations objects.
    """

    # treat None and empty list uniformly
    restrict_types = [] if restrict_types is None else restrict_types
    ignore_types   = [] if ignore_types is None else ignore_types

    matches = SearchMatchSet("Text marked with different types")

    # Dict-of-dicts, outer key annotation text, inner type,
    # values annotation objects.
    text_type_ann_map = {}
    
    for ann_obj in ann_objs:
        for t in ann_obj.get_textbounds():
            if t.type in ignore_types:
                continue

            if t.text not in text_type_ann_map:
                text_type_ann_map[t.text] = {}
            if t.type not in text_type_ann_map[t.text]:
                text_type_ann_map[t.text][t.type] = []
            text_type_ann_map[t.text][t.type].append((ann_obj,t))
    
    for text in text_type_ann_map:
        if len(text_type_ann_map[text]) < 2:
            # all matching texts have same type, OK
            continue

        types = text_type_ann_map[text].keys()
        # avoiding any() etc. to be compatible with python 2.4
        if restrict_types != [] and len([t for t in types if t in restrict_types]) == 0:
            # Does not involve any of the types restricted do
            continue

        # debugging
        #print >> sys.stderr, "Text marked with %d different types:\t%s\t: %s" % (len(text_type_ann_map[text]), text, ", ".join(["%s (%d occ.)" % (type, len(text_type_ann_map[text][type])) for type in text_type_ann_map[text]]))
        for type in text_type_ann_map[text]:
            for ann_obj, ann in text_type_ann_map[text][type]:
                # debugging
                #print >> sys.stderr, "\t%s %s" % (ann.source_id, ann)
                matches.add_match(ann_obj, ann)

    return matches

def check_consistency(ann_objs, restrict_types=[], ignore_types=[]):
    """
    Searches for inconsistent annotations in given Annotations
    objects.  Returns a list of SearchMatchSet objects, one for each
    checked criterion that generated matches for the search.
    """

    match_sets = []

    m = eq_text_neq_type_spans(ann_objs, restrict_types=restrict_types, ignore_types=ignore_types)
    if len(m) != 0:
        match_sets.append(m)

    return match_sets

def search_textbound(ann_objs, text, restrict_types=[], ignore_types=[]):
    """
    Searches for the given text in the Textbound annotations in the
    given Annotations objects.  Returns a SearchMatchSet object.
    """

    matches = SearchMatchSet("Textbound matching '%s'" % text)

    # treat None and empty list uniformly
    restrict_types = [] if restrict_types is None else restrict_types
    ignore_types   = [] if ignore_types is None else ignore_types
    
    for ann_obj in ann_objs:
        for t in ann_obj.get_textbounds():
            if t.type in ignore_types:
                continue
            if restrict_types != [] and t.type not in restrict_types:
                continue
            # TODO: make options for "text included" vs. "text matches"
            if text in t.text:
                matches.add_match(ann_obj, t)

    return matches

def search_text(ann_objs, text, restrict_types=[], ignore_types=[]):
    """
    Searches for the given text in the document texts of the given
    Annotations objects.  Returns a SearchMatchSet object.
    """

    # treat None and empty list uniformly
    restrict_types = [] if restrict_types is None else restrict_types
    ignore_types   = [] if ignore_types is None else ignore_types

    description = "Text matching '%s'" % text
    if restrict_types != []:
        description = description + ' (embedded in %s)' % (",".join(restrict_types))
    if ignore_types != []:
        description = description + ' (not embedded in %s)' % ",".join(ignore_types)
    matches = SearchMatchSet(description)

    for ann_obj in ann_objs:
        doctext = ann_obj.get_document_text()

        for m in re.finditer(r'\b('+text+r')\b', doctext):
            # only need to care about embedding annotations if there's
            # some annotation-based restriction
            #if restrict_types == [] and ignore_types == []:
            # TODO: _extremely_ naive and slow way to find embedding
            # annotations.  Use some reasonable data structure
            # instead.
            embedding = []
            for t in ann_obj.get_textbounds():
                if t.start <= m.start() and t.end >= m.end():
                    embedding.append(t)

            # Note interpretation of ignore_types here: if the text span
            # is embedded in one or more of the ignore_types, the match is
            # ignored.
            if len([e for e in embedding if e.type in ignore_types]) != 0:
                continue

            if restrict_types != [] and len([e for e in embedding if e.type in restrict_types]) == 0:
                continue

            # TODO: need a clean, standard way of identifying a text span
            # that does not involve an annotation; this is a bit of a hack
            tm = TextMatch(m.start(), m.end(), m.group())
            matches.add_match(ann_obj, tm)

    return matches

def format_results(matches):
    """
    Given matches to a search (a SearchMatchSet), formats the results
    for the client, returning a dictionary with the results in the
    expected format.
    """
    from document import relative_directory

    # the search response format is built similarly to that of the
    # directory listing.

    response = {}

    # header for search result browser
    response['itemhead'] = ['Document', 'Annotation', 'Type']
    
    response['items'] = []
    for ann_obj, ann in matches.get_matches():
        # NOTE: first "True" is to match format with directory listing,
        # second entry is non-listed "pointer" to annotation
        reld = relative_directory(ann_obj.get_document())
        response['items'].append([True, { 'edited' : [ann.id] }, reld, ann.id, ann.type])
    return response

def search_collection(directory, type, text):
    # TODO: this function is much too restricted in what it can do.
    # Despite the name, it can currently only search textbound
    # entitities. Extend its capabilities.

    ann_objs = __directory_to_annotations(directory)

    restrict_types = []
    if type is not None and type != "":
        restrict_types.append(type)

    matches = search_textbound(ann_objs, text, restrict_types=restrict_types)
        
    return format_results(matches)

def search_files_for_text(filenames, text, restrict_types=[], ignore_types=[]):
    """
    Searches for the given text in the given set of files.
    """
    anns = __filenames_to_annotations(filenames)
    return search_text(anns, text, restrict_types=restrict_types, ignore_types=ignore_types)

def search_files_for_textbound(filenames, text, restrict_types=[], ignore_types=[]):
    """
    Searches for the given text in textbound annotations in the given
    set of files.
    """
    anns = __filenames_to_annotations(filenames)
    return search_textbound(anns, text, restrict_types=restrict_types, ignore_types=ignore_types)

def check_files_consistency(filenames, restrict_types=[], ignore_types=[]):
    """
    Searches for inconsistent annotations in the given set of files.
    """
    anns = __filenames_to_annotations(filenames)
    return check_consistency(anns, restrict_types=restrict_types, ignore_types=ignore_types)

def argparser():
    import argparse

    ap=argparse.ArgumentParser(description="Search BioNLP Shared Task annotations.")
    ap.add_argument("-v", "--verbose", default=False, action="store_true", help="Verbose output.")
    ap.add_argument("-c", "--consistency", default=False, action="store_true", help="Search for inconsistent annotations.")
    ap.add_argument("-r", "--restrict", metavar="TYPE", nargs="+", help="Restrict to given types.")
    ap.add_argument("-i", "--ignore", metavar="TYPE", nargs="+", help="Ignore given types.")
    ap.add_argument("-t", "--text", metavar="TEXT", help="Search for matching text.")
    ap.add_argument("-b", "--textbound", metavar="TEXT", help="Search for textbound matching text.")
    ap.add_argument("files", metavar="FILE", nargs="+", help="Files to verify.")
    return ap

def main(argv=None):
    import sys
    import os

    if argv is None:
        argv = sys.argv
    arg = argparser().parse_args(argv[1:])

    # TODO: allow multiple searches
    if arg.text:
        matches = [search_files_for_text(arg.files, arg.text,
                                         restrict_types=arg.restrict,
                                         ignore_types=arg.ignore)]
    elif arg.textbound:
        matches = [search_files_for_textbound(arg.files, arg.textbound,
                                              restrict_types=arg.restrict,
                                              ignore_types=arg.ignore)]
    elif arg.consistency:
        matches = check_files_consistency(arg.files,
                                          restrict_types=arg.restrict,
                                          ignore_types=arg.ignore)
    else:
        print >> sys.stderr, "Please specify action (-h for help)"
        return 1

    for m in matches:
        print m.criterion
        for ann_obj, ann in m.get_matches():
            # TODO: get rid of "edited" hack to point to a document ("%5B0%5D%5B%5D"="[0][]")
            # TODO: get rid of specific URL hack and similar
            print "\thttp://localhost/brat/#/%s?edited%%5B0%%5D%%5B%%5D=%s (%s)" % (ann_obj.get_document().replace("data/",""), ann.id, str(ann).rstrip())

if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
