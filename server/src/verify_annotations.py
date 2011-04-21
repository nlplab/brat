#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

# Verification of BioNLP Shared Task - style annotations.

import sys
import os
import re
import argparse

import annotation
import annspec

from projectconfig import ProjectConfiguration

# Issue types. Values should match with annotation interface.
AnnotationError = "AnnotationError"
AnnotationWarning = "AnnotationWarning"
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

def contained_in_span(a1, a2):
    """
    Returns True if the first given TextBoundAnnotation is contained in the second, False otherwise.
    """
    return a1.start >= a2.start and a1.end <= a2.end

def verify_equivs(ann_obj, projectconfig):
    issues = []

    for eq in ann_obj.get_equivs():
        # get the equivalent annotations
        equiv_anns = [ann_obj.get_ann_by_id(eid) for eid in eq.entities]

        # all the types of the Equivalent entities have to match
        eq_type = {}
        for e in equiv_anns:
            eq_type[e.type] = True
        if len(eq_type) != 1:
            # more than one type
            # TODO: mark this error on the Eq relation, not the entities
            for e in equiv_anns:
                issues.append(AnnotationIssue(e.id, AnnotationError, "%s in Equiv relation involving entities of more than one type (%s)" % (e.id, ", ".join(eq_type.keys()))))

    return issues

def verify_entity_overlap(ann_obj, projectconfig):
    issues = []

    # check for overlap between physical entities
    physical_entities = [a for a in ann_obj.get_textbounds() if projectconfig.is_physical_entity_type(a.type)]
    overlapping = check_textbound_overlap(physical_entities)
    for a1, a2 in overlapping:
        if a1.start == a2.start and a1.end == a2.end:
            issues.append(AnnotationIssue(a1.id, AnnotationError, "Error: %s has identical span with %s %s" % (a1.type, a2.type, a2.id)))            
        elif contained_in_span(a1, a2):
            if a1.type not in annspec.allowed_entity_nestings.get(a2.type, annspec.allowed_entity_nestings['default']):
                issues.append(AnnotationIssue(a1.id, AnnotationError, "Error: %s cannot be contained in %s (%s)" % (a1.type, a2.type, a2.id)))
        elif contained_in_span(a2, a1):
            if a2.type not in annspec.allowed_entity_nestings.get(a1.type, annspec.allowed_entity_nestings['default']):
                issues.append(AnnotationIssue(a1.id, AnnotationError, "Error: %s cannot contain %s (%s)" % (a1.type, a2.type, a2.id)))
        else:
            # crossing boundaries; never allowed for physical entities.
            issues.append(AnnotationIssue(a1.id, AnnotationError, "Error: entity has crossing span with %s" % a2.id))
    
    # TODO: generalize to other cases
    return issues

def verify_annotation_types(ann_obj, projectconfig):
    issues = []

    event_types = projectconfig.get_event_types()
    textbound_types = event_types + projectconfig.get_entity_types()

    for e in ann_obj.get_events():
        if e.type not in event_types:
            issues.append(AnnotationIssue(e.id, AnnotationError, "Error: %s is not a known event type (check configuration?)" % e.type))

    for t in ann_obj.get_textbounds():
        if t.type not in textbound_types:
            issues.append(AnnotationIssue(t.id, AnnotationError, "Error: %s is not a known textbound type (check configuration?)" % t.type))

    return issues

def verify_triggers(ann_obj, projectconfig):
    issues = []

    events_by_trigger = {}

    for e in ann_obj.get_events():
        if e.trigger not in events_by_trigger:
            events_by_trigger[e.trigger] = []
        events_by_trigger[e.trigger].append(e)

    trigger_by_span_and_type = {}

    for t in ann_obj.get_textbounds():
        if not projectconfig.is_event_type(t.type):
            continue

        if t.id not in events_by_trigger:
            issues.append(AnnotationIssue(t.id, AnnotationIncomplete, "Warning: trigger %s is not referenced from any event" % t.id))

        spt = (t.start, t.end, t.type)
        if spt not in trigger_by_span_and_type:
            trigger_by_span_and_type[spt] = []
        trigger_by_span_and_type[spt].append(t)

    for spt in trigger_by_span_and_type:
        trigs = trigger_by_span_and_type[spt]
        if len(trigs) < 2:
            continue
        for t in trigs:
            # We currently need to attach these to events if
            # there are any; triggers referenced from events don't get
            # shown. TODO: revise once this is fixed.
            if t.id in events_by_trigger:
                issues.append(AnnotationIssue(events_by_trigger[t.id][0].id, AnnotationWarning, "Warning: triggers %s have identical span and type (harmless but unnecessary duplication)" % ",".join([x.id for x in trigs])))
            else:
                issues.append(AnnotationIssue(t.id, AnnotationWarning, "Warning: triggers %s have identical span and type (harmless but unnecessary duplication)" % ",".join([x.id for x in trigs])))

    return issues

def verify_annotation(ann_obj, projectconfig):
    """
    Verifies the correctness of a given AnnotationFile.
    Returns a list of AnnotationIssues.
    """
    issues = []

    issues += verify_annotation_types(ann_obj, projectconfig)

    issues += verify_equivs(ann_obj, projectconfig)

    issues += verify_entity_overlap(ann_obj, projectconfig)

    issues += verify_triggers(ann_obj, projectconfig)

    # various event type checks

    def event_nonum_args(e):
        # returns event arguments without trailing numbers
        # (e.g. "Theme1" -> "Theme").
        nna = {}
        for arg, aid in e.args:
            m = re.match(r'^(.*?)\d*$', arg)
            if m:
                arg = m.group(1)
            if arg not in nna:
                nna[arg] = []
            nna[arg].append(aid)
        return nna

    # check for events missing mandatory arguments
    for e in ann_obj.get_events():
        found_nonum_args = event_nonum_args(e)
        # TODO: don't hard-code what Themes are required for
        if "Theme" not in found_nonum_args and e.type != "Process":
            issues.append(AnnotationIssue(e.id, AnnotationIncomplete, "Theme required for event"))

    # check for events with disallowed arguments
    for e in ann_obj.get_events():
        allowed = projectconfig.arc_types_from(e.type)
        eargs = event_nonum_args(e)
        for a in eargs:
            if a not in allowed:
                issues.append(AnnotationIssue(e.id, AnnotationError, "Error: %s cannot take a %s argument" % (e.type, a)))
            else:
                for rid in eargs[a]:
                    r = ann_obj.get_ann_by_id(rid)
                    if a not in projectconfig.arc_types_from_to(e.type, r.type):
                        issues.append(AnnotationIssue(e.id, AnnotationError, "Error: %s argument %s cannot be of type %s" % (e.type, a, r.type)))

    # check for events with disallowed argument counts
    for e in ann_obj.get_events():
        found_nonum_args = event_nonum_args(e)
        for a in found_nonum_args:
            # TODO: don't hard-code what multiple arguments are allowed for
            if len(found_nonum_args[a]) > 1 and not (e.type == "Binding" and a in ("Theme", "Site")):
                issues.append(AnnotationIssue(e.id, AnnotationError, "Error: %s cannot take multiple %s arguments" % (e.type, a)))
    
    return issues

def main(argv=None):
    if argv is None:
        argv = sys.argv
    arg = argparser().parse_args(argv[1:])

    print >> sys.stderr, "TODO: implement command-line invocation"

if __name__ == "__main__":
    sys.exit(main())
