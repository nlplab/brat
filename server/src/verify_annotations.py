#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

# Verification of BioNLP Shared Task - style annotations.

from __future__ import with_statement

import os
import re

import annotation

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

    def human_readable_str(self):
        return "%s: %s\t%s" % (self.ann_id, self.type, self.description)

    def __str__(self):
        return "%s\t%s %s\t%s" % (self.id, self.type, self.ann_id, self.description)

def argparser():
    import argparse

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

def verify_equivs(ann_obj, projectconf):
    issues = []

    # TODO: get rid of hard-coded type label
    EQUIV_TYPE = "Equiv"

    # shortcut
    def disp(s):
        return projectconf.preferred_display_form(s)

    for eq in ann_obj.get_equivs():
        # get the equivalent annotations
        equiv_anns = [ann_obj.get_ann_by_id(eid) for eid in eq.entities]

        # all pairs of entity types in the Equiv group must be allowed
        # to have an Equiv. Create type-level pairs to avoid N^2
        # search where N=entities.
        eq_type = {}
        for e in equiv_anns:
            eq_type[e.type] = True
        type_pairs = []
        for t1 in eq_type:
            for t2 in eq_type:
                type_pairs.append((t1,t2))

        # do avoid marking both (a1,a2) and (a2,a1), remember what's
        # already included
        marked = {}

        for t1, t2 in type_pairs:
            reltypes = projectconf.relation_types_from_to(t1, t2)
            if EQUIV_TYPE not in reltypes:
                # Avoid redundant output
                if (t2,t1) in marked:
                    continue
                # TODO: mark this error on the Eq relation, not the entities
                for e in equiv_anns:
                    issues.append(AnnotationIssue(e.id, AnnotationError, "Equiv relation not allowed between %s and %s" % (disp(t1), disp(t2))))
                marked[(t1,t2)] = True

    return issues

def verify_entity_overlap(ann_obj, projectconf):
    issues = []

    # shortcut
    def disp(s):
        return projectconf.preferred_display_form(s)

    # Note: "ENTITY-NESTING" is a bit of a magic value in config. Might
    # want to use some other approach.
    nesting_relation = "ENTITY-NESTING"

    # check for overlap between physical entities
    physical_entities = [a for a in ann_obj.get_textbounds() if projectconf.is_physical_entity_type(a.type)]
    overlapping = check_textbound_overlap(physical_entities)
    for a1, a2 in overlapping:
        if a1.start == a2.start and a1.end == a2.end:
            issues.append(AnnotationIssue(a1.id, AnnotationError, "Error: %s has identical span with %s %s" % (disp(a1.type), disp(a2.type), a2.id)))            
        elif contained_in_span(a1, a2):
            if nesting_relation not in projectconf.relation_types_from_to(a1.type, a2.type):
                issues.append(AnnotationIssue(a1.id, AnnotationError, "Error: %s cannot be contained in %s (%s)" % (disp(a1.type), disp(a2.type), a2.id)))
        elif contained_in_span(a2, a1):
            if nesting_relation not in projectconf.relation_types_from_to(a2.type, a1.type):
                issues.append(AnnotationIssue(a1.id, AnnotationError, "Error: %s cannot contain %s (%s)" % (disp(a1.type), disp(a2.type), a2.id)))
        else:
            # crossing boundaries; never allowed for physical entities.
            issues.append(AnnotationIssue(a1.id, AnnotationError, "Error: annotation has crossing span with %s" % a2.id))
    
    # TODO: generalize to other cases
    return issues

def verify_annotation_types(ann_obj, projectconf):
    issues = []

    event_types = projectconf.get_event_types()
    textbound_types = event_types + projectconf.get_entity_types()
    relation_types = projectconf.get_relation_types()

    # shortcut
    def disp(s):
        return projectconf.preferred_display_form(s)

    for e in ann_obj.get_events():
        if e.type not in event_types:
            issues.append(AnnotationIssue(e.id, AnnotationError, "Error: %s is not a known event type (check configuration?)" % disp(e.type)))

    for t in ann_obj.get_textbounds():
        if t.type not in textbound_types:
            issues.append(AnnotationIssue(t.id, AnnotationError, "Error: %s is not a known textbound type (check configuration?)" % disp(t.type)))

    for r in ann_obj.get_relations():
        if r.type not in relation_types:
            issues.append(AnnotationIssue(r.id, AnnotationError, "Error: %s is not a known relation type (check configuration?)" % disp(r.type)))

    return issues

def verify_triggers(ann_obj, projectconf):
    issues = []

    events_by_trigger = {}

    for e in ann_obj.get_events():
        if e.trigger not in events_by_trigger:
            events_by_trigger[e.trigger] = []
        events_by_trigger[e.trigger].append(e)

    trigger_by_span_and_type = {}

    for t in ann_obj.get_textbounds():
        if not projectconf.is_event_type(t.type):
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
            # We currently need to attach these to events if there are
            # any; issues attached to triggers referenced from events
            # don't get shown. TODO: revise once this is fixed.
            if t.id in events_by_trigger:
                issues.append(AnnotationIssue(events_by_trigger[t.id][0].id, AnnotationWarning, "Warning: triggers %s have identical span and type (harmless but unnecessary duplication)" % ",".join([x.id for x in trigs])))
            else:
                issues.append(AnnotationIssue(t.id, AnnotationWarning, "Warning: triggers %s have identical span and type (harmless but unnecessary duplication)" % ",".join([x.id for x in trigs])))

    return issues

def verify_relations(ann_obj, projectconf):
    issues = []

    # shortcut
    def disp(s):
        return projectconf.preferred_display_form(s)

    for r in ann_obj.get_relations():
        # check for disallowed argument types
        a1 = ann_obj.get_ann_by_id(r.arg1)
        a2 = ann_obj.get_ann_by_id(r.arg2)
        reltypes = projectconf.relation_types_from_to(a1.type, a2.type)
        if r.type not in reltypes:
            issues.append(AnnotationIssue(r.id, AnnotationError, "Error: %s relation not allowed between %s and %s" % (disp(r.type), disp(a1.type), disp(a2.type))))

    return issues

def verify_annotation(ann_obj, projectconf):
    """
    Verifies the correctness of a given AnnotationFile.
    Returns a list of AnnotationIssues.
    """
    issues = []

    issues += verify_annotation_types(ann_obj, projectconf)

    issues += verify_equivs(ann_obj, projectconf)

    issues += verify_entity_overlap(ann_obj, projectconf)

    issues += verify_triggers(ann_obj, projectconf)

    issues += verify_relations(ann_obj, projectconf)

    # shortcut
    def disp(s):
        return projectconf.preferred_display_form(s)

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
        for m in projectconf.mandatory_arguments(e.type):
            if m not in found_nonum_args:
                issues.append(AnnotationIssue(e.id, AnnotationIncomplete, "%s required for event" % disp(m)))

    # check for events with disallowed arguments
    for e in ann_obj.get_events():
        allowed = projectconf.arc_types_from(e.type)
        eargs = event_nonum_args(e)
        for a in eargs:
            if a not in allowed:
                issues.append(AnnotationIssue(e.id, AnnotationError, "Error: %s cannot take a %s argument" % (disp(e.type), disp(a))))
            else:
                for rid in eargs[a]:
                    r = ann_obj.get_ann_by_id(rid)
                    if a not in projectconf.arc_types_from_to(e.type, r.type):
                        issues.append(AnnotationIssue(e.id, AnnotationError, "Error: %s argument %s cannot be of type %s" % (disp(e.type), disp(a), disp(r.type))))

    # check for events with disallowed argument counts
    for e in ann_obj.get_events():
        multiple_allowed = projectconf.multiple_allowed_arguments(e.type)
        found_nonum_args = event_nonum_args(e)
        for a in [m for m in found_nonum_args if len(found_nonum_args[m]) > 1]:
            if a not in multiple_allowed:
                issues.append(AnnotationIssue(e.id, AnnotationError, "Error: %s cannot take multiple %s arguments" % (disp(e.type), disp(a))))
    
    return issues

def main(argv=None):
    if argv is None:
        argv = sys.argv
    arg = argparser().parse_args(argv[1:])

    for fn in arg.files:
        try:
            projectconf = ProjectConfiguration(os.path.dirname(fn))
            # remove ".a2" or ".rel" suffixes for Annotations to prompt
            # parsing of .a1 also.
            nosuff_fn = fn.replace(".a2","").replace(".rel","")
            with annotation.TextAnnotations(nosuff_fn) as ann_obj:
                issues = verify_annotation(ann_obj, projectconf)
                for i in issues:
                    print "%s:\t%s" % (fn, i.human_readable_str())
        except annotation.AnnotationFileNotFoundError:
            print >> sys.stderr, "%s:\tFailed check: file not found" % fn
        except annotation.AnnotationNotFoundError, e:
            print >> sys.stderr, "%s:\tFailed check: %s" % (fn, e)

    if arg.verbose:
        print >> sys.stderr, "Check complete."

if __name__ == "__main__":
    import sys
    sys.exit(main())
