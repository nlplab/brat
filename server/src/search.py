#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

# Search-related functionality for BioNLP Shared Task - style
# annotations.

from __future__ import with_statement

import re
import annotation

from message import Messager

DEFAULT_EMPTY_STRING = "***"

REPORT_SEARCH_TIMINGS = False

if REPORT_SEARCH_TIMINGS:
    from sys import stderr
    from datetime import datetime

# TODO: nested_types restriction not consistently enforced in
# searches.

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

    def sort_matches(self):
        # sort by document name
        self.__matches.sort(lambda a,b: cmp(a[0].get_document(),b[0].get_document()))

    # TODO: would be better with an iterator
    def get_matches(self):
        return self.__matches

    def __len__(self):
        return len(self.__matches)

class TextMatch(object):
    """
    Represents a text span matching a query.
    """
    def __init__(self, start, end, text, sentence=None):
        self.start = start
        self.end = end
        self.text = text
        self.sentence = sentence

    def reference_id(self):
        # mimic reference_id for annotations
        return ["%s~%s" % (self.start, self.end)]

    def reference_text(self):
        return "%s-%s" % (self.start, self.end)

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

    global REPORT_SEARCH_TIMINGS
    if REPORT_SEARCH_TIMINGS:
        process_start = datetime.now()

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

    if REPORT_SEARCH_TIMINGS:
        process_delta = datetime.now() - process_start
        print >> stderr, "filenames_to_annotations: processed in", str(process_delta.seconds)+"."+str(process_delta.microseconds/10000), "seconds"

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

def _get_text_type_ann_map(ann_objs, restrict_types=[], ignore_types=[], nested_types=[]):
    """
    Helper function for search. Given annotations, returns a
    dict-of-dicts, outer key annotation text, inner type, values
    annotation objects.
    """

    # treat None and empty list uniformly
    restrict_types = [] if restrict_types is None else restrict_types
    ignore_types   = [] if ignore_types is None else ignore_types
    nested_types   = [] if nested_types is None else nested_types

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

    return text_type_ann_map

def _get_offset_ann_map(ann_objs, restrict_types=[], ignore_types=[]):
    """
    Helper function for search. Given annotations, returns a dict
    mapping offsets in text into the set of annotations spanning each
    offset.
    """

    # treat None and empty list uniformly
    restrict_types = [] if restrict_types is None else restrict_types
    ignore_types   = [] if ignore_types is None else ignore_types

    offset_ann_map = {}
    for ann_obj in ann_objs:
        for t in ann_obj.get_textbounds():
            if t.type in ignore_types:
                continue
            if restrict_types != [] and t.type not in restrict_types:
                continue

            for o in range(t.start, t.end):
                if o not in offset_ann_map:
                    offset_ann_map[o] = set()
                offset_ann_map[o].add(t)

    return offset_ann_map

def eq_text_neq_type_spans(ann_objs, restrict_types=[], ignore_types=[], nested_types=[]):
    """
    Searches for annotated spans that match in string content but
    disagree in type in given Annotations objects.
    """

    # treat None and empty list uniformly
    restrict_types = [] if restrict_types is None else restrict_types
    ignore_types   = [] if ignore_types is None else ignore_types
    nested_types   = [] if nested_types is None else nested_types

    # TODO: nested_types constraints not applied

    matches = SearchMatchSet("Text marked with different types")

    text_type_ann_map = _get_text_type_ann_map(ann_objs, restrict_types, ignore_types, nested_types)
    
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

def _get_offset_sentence_map(s):
    """
    Helper, sentence-splits and returns a mapping from character
    offsets to sentence number.
    """
    from ssplit import en_sentence_boundary_gen

    m = {} # TODO: why is this a dict and not an array?
    sprev, snum = 0, 1 # note: sentences indexed from 1
    for sstart, send in en_sentence_boundary_gen(s):
        # if there are extra newlines (i.e. more than one) in between
        # the previous end and the current start, those need to be
        # added to the sentence number
        snum += max(0,len([nl for nl in s[sprev:sstart] if nl == "\n"]) - 1)
        for o in range(sprev, send):
            m[o] = snum
        sprev = send
        snum += 1
    return m

def _split_and_tokenize(s):
    """
    Helper, sentence-splits and tokenizes, returns array comparable to
    what you would get from re.split(r'(\s+)', s).
    """
    from ssplit import en_sentence_boundary_gen
    from tokenise import en_token_boundary_gen

    tokens = []

    sprev = 0
    for sstart, send in en_sentence_boundary_gen(s):
        if sprev != sstart:
            # between-sentence space
            tokens.append(s[sprev:sstart])
        stext = s[sstart:send]
        tprev = sstart
        for tstart, tend in en_token_boundary_gen(stext):
            if tprev != tstart:
                # between-token space
                tokens.append(s[sstart+tprev:sstart+tstart])
            tokens.append(s[sstart+tstart:sstart+tend])
            tprev = tend
        sprev = send

    if sprev != len(s):
        # document-final space
        tokens.append(s[sprev:])

    assert "".join(tokens) == s, "INTERNAL ERROR\n'%s'\n'%s'" % ("".join(tokens),s)

    return tokens
        
def eq_text_partially_marked(ann_objs, restrict_types=[], ignore_types=[], nested_types=[]):
    """
    Searches for spans that match in string content but are not all
    marked.
    """

    # treat None and empty list uniformly
    restrict_types = [] if restrict_types is None else restrict_types
    ignore_types   = [] if ignore_types is None else ignore_types
    nested_types   = [] if nested_types is None else nested_types

    # TODO: check that constraints are properly applied

    matches = SearchMatchSet("Text marked partially")

    text_type_ann_map = _get_text_type_ann_map(ann_objs, restrict_types, ignore_types, nested_types)

    max_length_tagged = max([len(s) for s in text_type_ann_map])

    # TODO: faster and less hacky way to detect missing annotations
    text_untagged_map = {}
    for ann_obj in ann_objs:
        doctext = ann_obj.get_document_text()

        # TODO: proper tokenization.
        # NOTE: this will include space.
        #tokens = re.split(r'(\s+)', doctext)
        tokens = _split_and_tokenize(doctext)

        # document-specific map
        offset_ann_map = _get_offset_ann_map([ann_obj])

        # this one too
        sentence_num = _get_offset_sentence_map(doctext)

        start_offset = 0
        for start in range(len(tokens)):
            for end in range(start, len(tokens)):
                s = "".join(tokens[start:end])                
                end_offset = start_offset + len(s)

                if len(s) > max_length_tagged:
                    # can't hit longer strings, none tagged
                    break

                if s not in text_type_ann_map:
                    # consistently untagged
                    continue

                # Some matching is tagged; this is considered
                # inconsistent (for this check) if the current span
                # has no fully covering tagging. Note that type
                # matching is not considered here.
                start_spanning = offset_ann_map.get(start_offset, set())
                end_spanning = offset_ann_map.get(end_offset-1, set()) # NOTE: -1 needed, see _get_offset_ann_map()
                if len(start_spanning & end_spanning) == 0:
                    if s not in text_untagged_map:
                        text_untagged_map[s] = []
                    text_untagged_map[s].append((ann_obj, start_offset, end_offset, s, sentence_num[start_offset]))

            start_offset += len(tokens[start])

    # form match objects, grouping by text
    for text in text_untagged_map:
        assert text in text_type_ann_map, "INTERNAL ERROR"

        # collect tagged and untagged cases for "compressing" output
        # in cases where one is much more common than the other
        tagged   = []
        untagged = []

        for type in text_type_ann_map[text]:
            for ann_obj, ann in text_type_ann_map[text][type]:
                #matches.add_match(ann_obj, ann)
                tagged.append((ann_obj, ann))

        for ann_obj, start, end, s, snum in text_untagged_map[text]:
            # TODO: need a clean, standard way of identifying a text span
            # that does not involve an annotation; this is a bit of a hack
            tm = TextMatch(start, end, s, snum)
            #matches.add_match(ann_obj, tm)
            untagged.append((ann_obj, tm))

        # decide how to output depending on relative frequency
        freq_ratio_cutoff = 3
        cutoff_limit = 5

        if (len(tagged) > freq_ratio_cutoff * len(untagged) and 
            len(tagged) > cutoff_limit):
            # cut off all but cutoff_limit from tagged
            for ann_obj, m in tagged[:cutoff_limit]:
                matches.add_match(ann_obj, m)
            for ann_obj, m in untagged:
                matches.add_match(ann_obj, m)
            print "(note: omitting %d instances of tagged '%s')" % (len(tagged)-cutoff_limit, text)
        elif (len(untagged) > freq_ratio_cutoff * len(tagged) and
              len(untagged) > cutoff_limit):
            # cut off all but cutoff_limit from tagged
            for ann_obj, m in tagged:
                matches.add_match(ann_obj, m)
            for ann_obj, m in untagged[:cutoff_limit]:
                matches.add_match(ann_obj, m)
            print "(note: omitting %d instances of untagged '%s')" % (len(untagged)-cutoff_limit, text)
        else:
            # include all
            for ann_obj, m in tagged + untagged:
                matches.add_match(ann_obj, m)
            
    
    return matches

def check_consistency(ann_objs, restrict_types=[], ignore_types=[], nested_types=[]):
    """
    Searches for inconsistent annotations in given Annotations
    objects.  Returns a list of SearchMatchSet objects, one for each
    checked criterion that generated matches for the search.
    """

    match_sets = []

    print >> sys.stderr, "NOTE: TEMPORARILY SWITCHING OFF TYPE AGREEMENT CHECKING!"
#     m = eq_text_neq_type_spans(ann_objs, restrict_types=restrict_types, ignore_types=ignore_types, nested_types=nested_types)
#     if len(m) != 0:
#         match_sets.append(m)

    m = eq_text_partially_marked(ann_objs, restrict_types=restrict_types, ignore_types=ignore_types, nested_types=nested_types)
    if len(m) != 0:
        match_sets.append(m)

    return match_sets

def search_anns_for_textbound(ann_objs, text, restrict_types=[], ignore_types=[], nested_types=[]):
    """
    Searches for the given text in the Textbound annotations in the
    given Annotations objects.  Returns a SearchMatchSet object.
    """

    global REPORT_SEARCH_TIMINGS
    if REPORT_SEARCH_TIMINGS:
        process_start = datetime.now()

    # treat None and empty list uniformly
    restrict_types = [] if restrict_types is None else restrict_types
    ignore_types   = [] if ignore_types is None else ignore_types
    nested_types   = [] if nested_types is None else nested_types

    description = "Textbounds containing text '%s'" % text
    if restrict_types != []:
        description = description + ' (of type %s)' % (",".join(restrict_types))
    if nested_types != []:
        description = description + ' (nesting annotation of type %s)' % (",".join(nested_types))
    matches = SearchMatchSet(description)
    
    for ann_obj in ann_objs:
        # collect per-document (ann_obj) for sorting
        ann_matches = []
        for t in ann_obj.get_textbounds():
            if t.type in ignore_types:
                continue
            if restrict_types != [] and t.type not in restrict_types:
                continue
            # TODO: make options for "text included" vs. "text matches"
            if (text != None and text != "" and 
                text != DEFAULT_EMPTY_STRING and text not in t.text):
                continue
            if nested_types != []:
                # TODO: massively inefficient
                nested = [x for x in ann_obj.get_textbounds() if x != t and x.start >= t.start and x.end <= t.end]
                if len([x for x in nested if x.type in nested_types]) == 0:
                    continue

            ann_matches.append(t)

        # sort by start offset
        ann_matches.sort(lambda a,b: cmp((a.start,-a.end),(b.start,-b.end)))

        # add to overall collection
        for t in ann_matches:
            matches.add_match(ann_obj, t)    

    # sort by document name for output
    matches.sort_matches()

    if REPORT_SEARCH_TIMINGS:
        process_delta = datetime.now() - process_start
        print >> stderr, "search_anns_for_textbound: processed in", str(process_delta.seconds)+"."+str(process_delta.microseconds/10000), "seconds"

    return matches

def search_anns_for_relation(ann_objs, arg1, arg1type, arg2, arg2type, restrict_types=[], ignore_types=[]):
    """
    Searches the given Annotations objects for relation annotations
    matching the given specification. Returns a SearchMatchSet object.
    """

    global REPORT_SEARCH_TIMINGS
    if REPORT_SEARCH_TIMINGS:
        process_start = datetime.now()

    # treat None and empty list uniformly
    restrict_types = [] if restrict_types is None else restrict_types
    ignore_types   = [] if ignore_types is None else ignore_types

    # TODO: include args in description
    description = "Relations"
    if restrict_types != []:
        description = description + ' (of type %s)' % (",".join(restrict_types))
    matches = SearchMatchSet(description)
    
    for ann_obj in ann_objs:
        # collect per-document (ann_obj) for sorting
        ann_matches = []
        
        # binary relations and equivs need to be treated separately due
        # to different structure (not a great design there)
        for r in ann_obj.get_relations():
            if r.type in ignore_types:
                continue
            if restrict_types != [] and r.type not in restrict_types:
                continue

            # argument constraints
            if arg1 is not None or arg1type is not None:
                arg1ent = ann_obj.get_ann_by_id(r.arg1)
                if arg1 is not None and arg1 not in arg1ent.get_text():
                    continue
                if arg1type is not None and arg1type != arg1ent.type:
                    continue
            if arg2 is not None or arg2type is not None:
                arg2ent = ann_obj.get_ann_by_id(r.arg2)
                if arg2 is not None and arg2 not in arg2ent.get_text():
                    continue
                if arg2type is not None and arg2type != arg2.type:
                    continue
                
            ann_matches.append(r)

        for r in ann_obj.get_equivs():
            if r.type in ignore_types:
                continue
            if restrict_types != [] and r.type not in restrict_types:
                continue

            # argument constraints. This differs from that for non-equiv
            # for relations as equivs are symmetric, so the arg1-arg2
            # distinction can be ignored.

            # TODO: this can match the same thing twice, which most
            # likely isn't what a user expects: for example, having
            # 'Protein' for both arg1type and arg2type can still match
            # an equiv between 'Protein' and 'Gene'.
            match_found = False
            for arg, argtype in ((arg1, arg1type), (arg2, arg2type)):
                match_found = False
                for aeid in r.entities:
                    argent = ann_obj.get_ann_by_id(aeid)
                    if arg is not None and arg not in argent.get_text():
                        continue
                    if argtype is not None and argtype != argent.type:
                        continue
                    match_found = True
                    break
                if not match_found:
                    break
            if not match_found:
                continue

            ann_matches.append(r)

        # TODO: sort, e.g. by offset of participant occurring first
        #ann_matches.sort(lambda a,b: cmp(???))

        # add to overall collection
        for r in ann_matches:
            matches.add_match(ann_obj, r)

    # sort by document name for output
    matches.sort_matches()

    if REPORT_SEARCH_TIMINGS:
        process_delta = datetime.now() - process_start
        print >> stderr, "search_anns_for_relation: processed in", str(process_delta.seconds)+"."+str(process_delta.microseconds/10000), "seconds"

    return matches

def search_anns_for_event(ann_objs, trigger_text, args, restrict_types=[], ignore_types=[]):
    """
    Searches the given Annotations objects for Event annotations
    matching the given specification. Returns a SearchMatchSet object.
    """

    global REPORT_SEARCH_TIMINGS
    if REPORT_SEARCH_TIMINGS:
        process_start = datetime.now()

    # treat None and empty list uniformly
    restrict_types = [] if restrict_types is None else restrict_types
    ignore_types   = [] if ignore_types is None else ignore_types

    # TODO: include args in description
    description = "Event triggered by text containing '%s'" % trigger_text
    if restrict_types != []:
        description = description + ' (of type %s)' % (",".join(restrict_types))
    matches = SearchMatchSet(description)
    
    for ann_obj in ann_objs:
        # collect per-document (ann_obj) for sorting
        ann_matches = []

        for e in ann_obj.get_events():
            if e.type in ignore_types:
                continue
            if restrict_types != [] and e.type not in restrict_types:
                continue

            try:
                t_ann = ann_obj.get_ann_by_id(e.trigger)
            except:
                # TODO: specific exception
                Messager.error('Failed to retrieve trigger annotation %s, skipping event %s in search' % (e.trigger, e.id))

            # TODO: make options for "text included" vs. "text matches"
            if (trigger_text != None and trigger_text != "" and 
                trigger_text != DEFAULT_EMPTY_STRING and 
                trigger_text not in t_ann.text):
                continue

            # argument constraints
            missing_match = False
            for arg in args:
                for s in ('role', 'type', 'text'):
                    assert s in arg, "Error: missing mandatory field '%s' in event search" % s
                found_match = False
                for role, aid in e.args:
                    if arg['role'] is not None and arg['role'] != '' and arg['role'] != role:
                        # mismatch on role
                        continue
                    arg_ent = ann_obj.get_ann_by_id(aid)
                    if (arg['type'] is not None and arg['type'] != '' and 
                        arg['type'] != arg_ent.type):
                        # mismatch on type
                        continue
                    if (arg['text'] is not None and arg['text'] != '' and
                        arg['text'] not in arg_ent.get_text()):
                        # mismatch on text
                        continue
                    found_match = True
                    break
                if not found_match:
                    missing_match = True
                    break
            if missing_match:
                continue

            ann_matches.append((t_ann, e))

        # sort by trigger start offset
        ann_matches.sort(lambda a,b: cmp((a[0].start,-a[0].end),(b[0].start,-b[0].end)))

        # add to overall collection
        for t_obj, e in ann_matches:
            matches.add_match(ann_obj, e)

    # sort by document name for output
    matches.sort_matches()

    if REPORT_SEARCH_TIMINGS:
        process_delta = datetime.now() - process_start
        print >> stderr, "search_anns_for_event: processed in", str(process_delta.seconds)+"."+str(process_delta.microseconds/10000), "seconds"

    return matches

def search_anns_for_text(ann_objs, text, restrict_types=[], ignore_types=[], nested_types=[]):
    """
    Searches for the given text in the document texts of the given
    Annotations objects.  Returns a SearchMatchSet object.
    """

    global REPORT_SEARCH_TIMINGS
    if REPORT_SEARCH_TIMINGS:
        process_start = datetime.now()

    # treat None and empty list uniformly
    restrict_types = [] if restrict_types is None else restrict_types
    ignore_types   = [] if ignore_types is None else ignore_types
    nested_types   = [] if nested_types is None else nested_types

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
            # if there are no type restrictions, we can skip this bit
            if restrict_types != [] or ignore_types != []:
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

    if REPORT_SEARCH_TIMINGS:
        process_delta = datetime.now() - process_start
        print >> stderr, "search_anns_for_text: processed in", str(process_delta.seconds)+"."+str(process_delta.microseconds/10000), "seconds"

    return matches

def format_results(matches):
    """
    Given matches to a search (a SearchMatchSet), formats the results
    for the client, returning a dictionary with the results in the
    expected format.
    """
    # decided to give filename only, remove this bit if the decision
    # sticks
#     from document import relative_directory
    from os.path import basename

    # the search response format is built similarly to that of the
    # directory listing.

    response = {}

    # fill in header for search result browser
    response['header'] = [('Document', 'string'), 
                          ('Annotation', 'string')]

    # determine which additional fields can be shown; depends on the
    # type of the results

    # TODO: this is much uglier than necessary, revise
    include_type = True
    try:
        for ann_obj, ann in matches.get_matches():
            ann.type
    except AttributeError:
        include_type = False

    include_text = True
    try:
        for ann_obj, ann in matches.get_matches():
            ann.text
    except AttributeError:
        include_text = False

    include_trigger_text = True
    try:
        for ann_obj, ann in matches.get_matches():
            ann.trigger
    except AttributeError:
        include_trigger_text = False

    if include_type:
        response['header'].append(('Type', 'string'))

    if include_text:
        response['header'].append(('Text', 'string'))

    if include_trigger_text:
        response['header'].append(('Trigger text', 'string'))

    # fill in content
    items = []
    for ann_obj, ann in matches.get_matches():
        # First value ("a") signals that the item points to a specific
        # annotation, not a collection (directory) or document.
        # second entry is non-listed "pointer" to annotation
        fn = basename(ann_obj.get_document())
        items.append(["a", { 'focus' : [ann.reference_id()] }, fn, ann.reference_text()])
        if include_type:
            items[-1].append(ann.type)
        if include_text:
            items[-1].append(ann.text)
        if include_trigger_text:
            try:
                items[-1].append(ann_obj.get_ann_by_id(ann.trigger).text)
            except:
                # TODO: specific exception
                items[-1].append("(ERROR)")
    response['items'] = items
    return response

### per-directory interface functions ###

def search_text(collection, text):
    directory = collection

    ann_objs = __directory_to_annotations(directory)

    matches = search_anns_for_text(ann_objs, text)
        
    results = format_results(matches)
    results['collection'] = directory
    
    return results

def search_entity(collection, type=None, text=DEFAULT_EMPTY_STRING):
    directory = collection

    ann_objs = __directory_to_annotations(directory)

    restrict_types = []
    if type is not None and type != "":
        restrict_types.append(type)

    matches = search_anns_for_textbound(ann_objs, text, restrict_types=restrict_types)
        
    results = format_results(matches)
    results['collection'] = directory
    
    return results

def search_event(collection, type=None, trigger=DEFAULT_EMPTY_STRING, args={}):
    directory = collection

    ann_objs = __directory_to_annotations(directory)

    restrict_types = []
    if type is not None and type != "":
        restrict_types.append(type)

    # to get around lack of JSON object parsing in dispatcher, parse
    # args here. 
    # TODO: parse JSON in dispatcher; this is far from the right place to do this..
    from jsonwrap import loads
    args = loads(args)

    matches = search_anns_for_event(ann_objs, trigger, args, restrict_types=restrict_types)

    results = format_results(matches)
    results['collection'] = directory
    
    return results

def search_relation(collection, type=None, arg1=None, arg1type=None, arg2=None, arg2type=None):
    directory = collection

    ann_objs = __directory_to_annotations(directory)

    restrict_types = []
    if type is not None and type != "":
        restrict_types.append(type)

    matches = search_anns_for_relation(ann_objs, arg1, arg1type, arg2, arg2type, restrict_types=restrict_types)

    results = format_results(matches)
    results['collection'] = directory
    
    return results

### filename list interface functions (e.g. command line) ###

def search_files_for_text(filenames, text, restrict_types=[], ignore_types=[], nested_types=[]):
    """
    Searches for the given text in the given set of files.
    """
    anns = __filenames_to_annotations(filenames)
    return search_anns_for_text(anns, text, restrict_types=restrict_types, ignore_types=ignore_types, nested_types=nested_types)

def search_files_for_textbound(filenames, text, restrict_types=[], ignore_types=[], nested_types=[]):
    """
    Searches for the given text in textbound annotations in the given
    set of files.
    """
    anns = __filenames_to_annotations(filenames)
    return search_anns_for_textbound(anns, text, restrict_types=restrict_types, ignore_types=ignore_types, nested_types=nested_types)

# TODO: filename list interface functions for event and relation search

def check_files_consistency(filenames, restrict_types=[], ignore_types=[], nested_types=[]):
    """
    Searches for inconsistent annotations in the given set of files.
    """
    anns = __filenames_to_annotations(filenames)
    return check_consistency(anns, restrict_types=restrict_types, ignore_types=ignore_types, nested_types=nested_types)

def argparser():
    import argparse

    ap=argparse.ArgumentParser(description="Search BioNLP Shared Task annotations.")
    ap.add_argument("-v", "--verbose", default=False, action="store_true", help="Verbose output.")
    ap.add_argument("-c", "--consistency", default=False, action="store_true", help="Search for inconsistent annotations.")
    ap.add_argument("-t", "--text", metavar="TEXT", help="Search for matching text.")
    ap.add_argument("-b", "--textbound", metavar="TEXT", help="Search for textbound matching text.")
    ap.add_argument("-r", "--restrict", metavar="TYPE", nargs="+", help="Restrict to given types.")
    ap.add_argument("-i", "--ignore", metavar="TYPE", nargs="+", help="Ignore given types.")
    ap.add_argument("-n", "--nested", metavar="TYPE", nargs="+", help="Require type to be nested.")
    ap.add_argument("files", metavar="FILE", nargs="+", help="Files to verify.")
    return ap

def main(argv=None):
    import sys
    import os

    if argv is None:
        argv = sys.argv
    arg = argparser().parse_args(argv[1:])

    # TODO: allow multiple searches
    if arg.textbound is not None:
        matches = [search_files_for_textbound(arg.files, arg.textbound,
                                              restrict_types=arg.restrict,
                                              ignore_types=arg.ignore,
                                              nested_types=arg.nested)]
    elif arg.text is not None:
        matches = [search_files_for_text(arg.files, arg.text,
                                         restrict_types=arg.restrict,
                                         ignore_types=arg.ignore,
                                         nested_types=arg.nested)]
    elif arg.consistency is not None:
        matches = check_files_consistency(arg.files,
                                          restrict_types=arg.restrict,
                                          ignore_types=arg.ignore,
                                          nested_types=arg.nested)
    else:
        print >> sys.stderr, "Please specify action (-h for help)"
        return 1

    for m in matches:
        print m.criterion
        for ann_obj, ann in m.get_matches():
            # TODO: get rid of "edited" hack to point to a document ("%5B0%5D%5B%5D"="[0][]")
            # TODO: get rid of specific URL hack and similar
            try:
                if ann.id not in (None, ""):
                    refstr = "?edited%%5B0%%5D%%5B%%5D=%s" % ann.id
                elif ann.sentence is not None:
                    # generate sentence reference
                    refstr = "?edited%%5B0%%5D%%5B%%5D=sent&edited%%5B0%%5D%%5B%%5D=%d" % ann.sentence
                else:
                    refstr = ""
            except:
                refstr = ""
                raise
            print "\thttp://localhost/stav/#/%s%s (%s)" % (ann_obj.get_document().replace("data/",""), refstr, str(ann).rstrip())

if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
