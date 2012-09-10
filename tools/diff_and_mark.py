#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:


# Preamble {{{
from __future__ import with_statement

'''
Mark the differences between two annotation files, creating a diff annotation
'''

try:
    import annotation
except ImportError:
    import os.path
    from sys import path as sys_path
    # Guessing that we might be in the brat tools/ directory ...
    sys_path.append(os.path.join(os.path.dirname(__file__), '../server/src'))
    import annotation

# this seems to be necessary for annotations to find its config
sys_path.append(os.path.join(os.path.dirname(__file__), '..'))
# }}}




class Mapping: # {{{
    def __init__(self):
        self.first_by_second = dict()
        self.second_by_first = dict()
        self.only_in_second = []
    def add(self, first, second, is_clone=False):
        self.first_by_second[second] = first
        self.second_by_first[first] = second
        if is_clone:
            self.only_in_second.append(second)
    def get_second(self, first):
        return self.second_by_first[first] if first in self.second_by_first else None
    def get_first(self, second):
        return self.first_by_second[second] if second in self.first_by_second else None
    def is_only_in_second(second):
        return second in self.only_in_second
    def is_only_in_first(first):
        return first in self.second_by_first
# }}}


class AnnotationDiff: # {{{
    def __init__(self, first, second, result): # {{{
        self.first = first
        self.second = second
        self.result = result
        self.mapping = Mapping()
    # }}}

    def diff(self): # {{{
        # self.second_triggers = [t for t in self.second.get_triggers()]

        self.diff_textbounds()
        self.diff_oneline_comments()
        self.diff_equivs()
        # TODO
        # self.diff_normalizations()
        # self.diff_attributes()
        # self.diff_relations()
        # self.diff_events()
    # }}}


    # Utilities for adding marks {{{
    def add_mark(self, type, target, reason):
        self.result.add_annotation(annotation.OnelineCommentAnnotation(
                target,
                self.result.get_new_id('#'),
                type,
                "\t" + reason))

    def add_missing(self, target, reason):
        self.add_mark('MissingAnnotation', target, reason)

    def add_added(self, target, reason):
        self.add_mark('AddedAnnotation', target, reason)

    def add_changed(self, target, reason):
        self.add_mark('ChangedAnnotation', target, reason)
    # }}}


    # Textbounds {{{
    def find_textbound(self, haystack, needle):
        for textbound in haystack.get_textbounds():
            if textbound.same_span(needle):
                return textbound
        return None

    def has_textbound(self, haystack, needle):
        return (self.find_textbound(haystack, needle) is not None)

    def diff_textbounds(self):
        for textbound in self.second.get_textbounds():
            found_first = self.find_textbound(self.first, textbound)
            if found_first is None:
                self.add_added(textbound.id, 'Added textbound')
            else:
                self.mapping.add(textbound.id, found_first.id)
        import copy
        for textbound in self.first.get_textbounds():
            if not self.has_textbound(self.second, textbound):
                clone = copy.copy(textbound)
                clone.id = self.result.get_new_id('T')
                self.result.add_annotation(clone)
                self.mapping.add(clone.id, textbound.id, True)
                self.add_missing(clone.id, 'Missing textbound')
    # }}}


    # One-line Comments {{{
    def has_oneline_comment(self, haystack, needle, target):
        for oneline_comment in haystack.get_oneline_comments():
            if oneline_comment.target == target and oneline_comment.get_text() == needle.get_text():
                return True
        return False

    def diff_oneline_comments(self):
        for oneline_comment in self.second.get_oneline_comments():
            target_in_first = self.mapping.get_first(oneline_comment.target)
            if not self.has_oneline_comment(self.first, oneline_comment, target_in_first):
                self.add_changed(oneline_comment.target, 'Added %s: "%s"' % (oneline_comment.type, oneline_comment.get_text()))
        for oneline_comment in self.first.get_oneline_comments():
            target_in_second = self.mapping.get_second(oneline_comment.target)
            if not self.has_oneline_comment(self.second, oneline_comment, target_in_second):
                self.add_changed(target_in_second, 'Missing %s: "%s"' % (oneline_comment.type, oneline_comment.get_text()))
    # }}}


    # Equivs {{{
    def diff_equivs(self):
        correspondence_map = dict()
        self.second_equivs = [equiv.entities for equiv in self.second.get_equivs()]
        for equiv_group, equiv in enumerate(self.second_equivs):
            for entity in equiv:
                correspondence_map[entity] = [None, equiv_group]
        self.first_equivs = [equiv.entities for equiv in self.first.get_equivs()]
        for equiv_group, equiv in enumerate(self.first_equivs):
            for self.first_entity in equiv:
                entity = self.mapping.get_second(self.first_entity)
                if entity in correspondence_map:
                    correspondence_map[entity][0] = equiv_group
                else:
                    correspondence_map[entity] = [equiv_group, None]

        correspondence_hist = dict()
        for entity in correspondence_map.keys():
            key = "%s-%s" % tuple(correspondence_map[entity])
            if key not in correspondence_hist:
                correspondence_hist[key] = [1, correspondence_map[entity], [entity]]
            else:
                correspondence_hist[key][0] += 1
                correspondence_hist[key][2].append(entity)

        seen_second = []
        seen_first = []
        import operator
        sorted_hist = sorted(correspondence_hist.iteritems(), key=operator.itemgetter(1))
        for key, equiv_item in sorted_hist:
            count, correspondence_pair, entities = equiv_item
            self.first_group, self.second_group = correspondence_pair
            for entity in entities:
                if self.first_group is None:
                    self.add_changed(entity, 'Added to equiv')
                elif self.second_group is None:
                    rest = [other for other in self.first_equivs[self.first_group] if other != entity]
                    self.add_changed(entity, 'Missing from equiv with %s' % ', '.join(rest))
                    rest = [other for other in self.first_equivs[self.first_group] if other != entity]
                elif self.first_group in seen_first or self.second_group in seen_second:
                    self.add_changed(entity, 'Changed from equiv %s' % ', '.join(rest))
                else:
                    seen_first.append(self.first_group)
                    seen_second.append(self.second_group)
    # }}}
# }}}


# Diff two files {{{
def copy_annotations(original_name, new_name):
    import shutil
    shutil.copyfile(original_name[0:-4] + '.txt', new_name[0:-4] + '.txt')
    shutil.copyfile(original_name, new_name)
    return annotation.Annotations(new_name)

def diff_files(first_name, second_name, result_name):
    # XXX TODO error handling
    first = annotation.Annotations(first_name)
    second = annotation.Annotations(second_name)
    result = copy_annotations(second_name, result_name)

    with result:
        AnnotationDiff(first, second, result).diff()
# }}}






# Command-line invocation {{{
def argparser():
    import argparse

    ap=argparse.ArgumentParser(description="Diff two annotation files, creating a diff annotation file")
    # ap.add_argument("-v", "--verbose", default=False, action="store_true", help="Verbose output.")
    ap.add_argument("first", metavar="FIRST", help="Original file, or gold standard (or directory)")
    ap.add_argument("second", metavar="SECOND", help="Changed file, or tested file (or directory)")
    ap.add_argument("result", metavar="SECOND", help="Diff annotation file to create (or directory)")
    return ap

def main(argv=None):
    from os.path import isdir

    if argv is None:
        argv = sys.argv
    options = argparser().parse_args(argv[1:])

    # XXX TODO DEBUG real argument handling
    diff_files('data/one/PMID-10086714.ann', 'data/two/PMID-10086714.ann', 'data/result/PMID-10086714.ann')

if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
# }}}
