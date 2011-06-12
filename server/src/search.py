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

    def get_matches(self):
        return self.__matches

    def __len__(self):
        return len(self.__matches)

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

    # treat uniformly
    if restrict_types is None:
        restrict_types = []
    if ignore_types is None:
        ignore_types = []

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

def search_for_text(ann_objs, text, restrict_types=[], ignore_types=[]):
    """
    Searches for the given text in the given Annotations
    objects.  Returns a SearchMatchSet objects.
    """

    # treat uniformly
    if restrict_types is None:
        restrict_types = []
    if ignore_types is None:
        ignore_types = []

    matches = SearchMatchSet("Textbound matching '%s'" % text)
    
    for ann_obj in ann_objs:
        for t in ann_obj.get_textbounds():
            if t.type in ignore_types:
                continue
            if restrict_types != [] and t.type not in restrict_types:
                continue
            if t.text == text:
                matches.add_match(ann_obj, t)

    return matches

def search_annotations(ann_objs, type, text):
    restrict_types = []
    if type is not None and type != "":
        restrict_types.append(type)

    # Old attempt, confirm unnecessary and remove
#     # TODO: more comprehensive search, not just textbounds
#     for t in ann_obj.get_textbounds():
#         if t.type == type:
#             # TODO: regexs
#             if text == t.text:
#                 # TODO XXX debugging
#                 #matches.add_match(ann_obj.get_document(), t.id)
#                 Messager.info("search_annotations: match %s %s in %s %s" % (text, type, ann_obj.get_document(), t.id))

#     return matches

    return search_for_text(ann_objs, text, restrict_types=restrict_types)


def search_collection(directory, type, text):
    ann_objs = __directory_to_annotations(directory)

    # Old attempt, confirm unnecessary and remove
#     matches = SearchMatchSet("Type %s containing text %s" % (type, text))

#     for ann_obj in anns:
#         m = search_annotations(ann_obj, type, text)
#         # TODO: need a way to extend SearchMatchSet with another
#         for ao, a in m.get_matches():
#             matches.add_match(ao, a)

    matches = search_annotations(ann_objs, type, text)

    response = {}

    response['results'] = []
    for ann_obj, ann in matches.get_matches():
        # TODO: remove once response is being read
        Messager.info("Match in %s %s" % (ann_obj.get_document(), ann.id))
        # TODO: note, debugging currently, ann_obj and ann are strings
        #response['results'].append((ann_obj.get_document(), ann.id))
        
    return response

def search_files_for_text(filenames, text, restrict_types=[], ignore_types=[]):
    """
    Searches for the given text in the given set of files.
    """

    anns = __filenames_to_annotations(filenames)

    return search_for_text(anns, text, restrict_types=[], ignore_types=[])

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
    ap.add_argument("-t", "--text", metavar="TEXT", help="Search for textbound matching text.")
    ap.add_argument("files", metavar="FILE", nargs="+", help="Files to verify.")
    return ap

def main(argv=None):
    import sys
    import os

    if argv is None:
        argv = sys.argv
    arg = argparser().parse_args(argv[1:])

    if arg.text:
        matches = [search_files_for_text(arg.files, arg.text,
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
    sys.exit(main())
