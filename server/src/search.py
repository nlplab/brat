#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

# Search-related functionality for BioNLP Shared Task - style
# annotations.

from __future__ import with_statement

import annotation

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

def check_file_consistency(filenames, restrict_types=[], ignore_types=[]):
    """
    Searches for inconsistent annotations in the given set of files.
    """
    anns = []
    for fn in filenames:
        try:
            # remove suffixes for Annotations to prompt parsing of .a1
            # also.
            nosuff_fn = fn.replace(".ann","").replace(".a2","").replace(".rel","")
            ann_obj = annotation.TextAnnotations(nosuff_fn)
            anns.append(ann_obj)
        except annotation.AnnotationFileNotFoundError:
            print >> sys.stderr, "%s:\tFailed: file not found" % fn
        except annotation.AnnotationNotFoundError, e:
            print >> sys.stderr, "%s:\tFailed: %s" % (fn, e)

    if len(anns) != len(filenames):
        print >> sys.stderr, "Note: only checking %d/%d given files" % (len(anns), len(filenames))

    return check_consistency(anns, restrict_types=restrict_types, ignore_types=ignore_types)

def output_file_consistency(filenames, out, restrict_types=[], ignore_types=[]):
    for ms in check_file_consistency(filenames, restrict_types=restrict_types, ignore_types=ignore_types):
        print >> out, ms.criterion
        for ann_obj, ann in ms.get_matches():
            # TODO: get rid of "edited" hack to point to a document ("%5B0%5D%5B%5D"="[0][]")
            # TODO: get rid of specific URL hack and similar
            print >> out, "\thttp://localhost/brat/#/%s?edited%%5B0%%5D%%5B%%5D=%s (%s)" % (ann_obj.get_document().replace("data/",""), ann.id, str(ann).rstrip())

def argparser():
    import argparse

    ap=argparse.ArgumentParser(description="Search BioNLP Shared Task annotations.")
    ap.add_argument("-v", "--verbose", default=False, action="store_true", help="Verbose output.")
    ap.add_argument("-c", "--consistency", default=False, action="store_true", help="Search for inconsistent annotations.")
    ap.add_argument("-r", "--restrict", metavar="TYPE", nargs="+", help="Restrict to given types.")
    ap.add_argument("-i", "--ignore", metavar="TYPE", nargs="+", help="Ignore given types.")
    ap.add_argument("files", metavar="FILE", nargs="+", help="Files to verify.")
    return ap

def main(argv=None):
    import sys
    import os

    if argv is None:
        argv = sys.argv
    arg = argparser().parse_args(argv[1:])

    if arg.consistency:
        output_file_consistency(arg.files, sys.stdout, restrict_types=arg.restrict,
                                ignore_types=arg.ignore)
    else:
        print >> sys.stderr, "Sorry, only supporting consistency check (-c) at the moment."
        

if __name__ == "__main__":
    import sys
    sys.exit(main())
