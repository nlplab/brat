#!/usr/bin/env python

# Verification of BioNLP Shared Task - style annotations.

import sys
import os
import argparse

import annspec

# Issue types. Values should match with annotation interface.
AnnotationError = "AnnotationError"
AnnotationIncomplete = "AnnotationIncomplete"

class AnnotationIssue:
    """
    Represents an issue noted in verification of annotations.
    """

    _next_id_idx = 1

    def __init__(self, ann_id, type, description=""):
        self.id = "#%d" % AnnotationIssue._next_id_idx
        AnnotationIssue._next_id_idx += 1
        self.ann_id, self.type, self.description = ann_id, type, description
        if self.description is None:
            self.description = ""

    def __str__(self):
        return "%s\t%s %s\t%s" % (self.id, self.type, self.ann_id, self.description)

def argparser():
    ap=argparse.ArgumentParser(description="Verify BioNLP Shared Task annotations.")
    ap.add_argument("-v", "--verbose", default=False, action="store_true", help="Verbose output.")
    ap.add_argument("files", metavar="FILE", nargs="+", help="Files to verify.")
    return ap

def check_textbound_overlap(anns):
    """
    Checks for overlap between the given TextBoundAnnotations.
    Returns a list of pairs of overlapping annotations.
    """
    overlapping = []

    for a1 in anns:
        for a2 in anns:
            if a1 is a2:
                continue
            if a2.start < a1.end and a2.end > a1.start:
                overlapping.append((a1,a2))

    return overlapping

def verify_annotation(ann_obj):
    """
    Verifies the correctness of a given AnnotationFile.
    Returns a list of AnnotationIssues.
    """
    issues = []

    # check for overlap between physical entities
    physical_entities = [a for a in ann_obj.get_textbounds() if a.type in annspec.physical_entity_types]
    overlapping = check_textbound_overlap(physical_entities)
    for a1, a2 in overlapping:
        issues.append(AnnotationIssue(a1.id, AnnotationError, "Error: %s cannot overlap a %s (%s)" % (a1.type, a2.type, a2.id)))
    
    # TODO: generalize to other cases

#     # group textbounds by type
#     textbounds_by_type = {}
#     for a in ann_obj.get_textbounds():
#         if a.type not in textbounds_by_type:
#             textbounds_by_type[a.type] = []
#         textbounds_by_type[a.type].append(a)
#
#     # check for overlap between textbounds that should not have any
#     for type in textbounds_by_type:
#         if type not in annspec.no_sametype_overlap_textbound_types:
#             # overlap OK
#             continue
#
#         overlapping = check_textbound_overlap(textbounds_by_type[type])
#
#         for a1, a2 in overlapping:
#             issues.append(AnnotationIssue(a1.id, AnnotationError, "Error: %s cannot overlap another entity (%s) of the same type" % (a1.type, a2.id)))

    # check for events missing mandatory arguments
    for e in ann_obj.get_events():
        found_args = {}
        for arg, aid in e.args:
            found_args[arg] = True
        # TODO: don't hard-code what Themes are required for
        if "Theme" not in found_args and e.type != "Process":
            issues.append(AnnotationIssue(e.id, AnnotationIncomplete, "Theme required for event"))

    return issues

def main(argv=None):
    if argv is None:
        argv = sys.argv
    arg = argparser().parse_args(argv[1:])

    print >> sys.stderr, "TODO: implement command-line invocation"

if __name__ == "__main__":
    sys.exit(main())
