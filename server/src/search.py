#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

# Search-related functionality for BioNLP Shared Task - style
# annotations.

from __future__ import with_statement

import re
import annotation

from message import Messager

### Constants
DEFAULT_EMPTY_STRING = "***"
REPORT_SEARCH_TIMINGS = False
DEFAULT_RE_FLAGS = re.UNICODE
###

if REPORT_SEARCH_TIMINGS:
    from sys import stderr
    from datetime import datetime

# Search result number may be restricted to limit server load and
# communication issues for searches in large collections that (perhaps
# unintentionally) result in very large numbers of hits
try:
    from config import MAX_SEARCH_RESULT_NUMBER
except ImportError:
    # unlimited
    MAX_SEARCH_RESULT_NUMBER = -1

# TODO: nested_types restriction not consistently enforced in
# searches.

class SearchMatchSet(object):
    """
    Represents a set of matches to a search. Each match is represented
    as an (ann_obj, ann) pair, where ann_obj is an Annotations object
    an ann an Annotation belonging to the corresponding ann_obj.
    """

    def __init__(self, criterion, matches=None):
        if matches is None:
            matches = []
        self.criterion = criterion
        self.__matches = matches

    def add_match(self, ann_obj, ann):
        self.__matches.append((ann_obj, ann))

    def sort_matches(self):
        # sort by document name
        self.__matches.sort(lambda a,b: cmp(a[0].get_document(),b[0].get_document()))

    def limit_to(self, num):
        # don't limit to less than one match
        if len(self.__matches) > num and num > 0:
            self.__matches = self.__matches[:num]
            return True
        else:
            return False

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

    def first_start(self):
        # mimic first_start() for TextBoundAnnotation
        return self.start

    def last_end(self):
        # mimic last_end() for TextBoundAnnotation
        return self.end
        
    def reference_id(self):
        # mimic reference_id for annotations
        # this is the form expected by client Util.param()
        return [self.start, self.end]

    def reference_text(self):
        return "%s-%s" % (self.start, self.end)

    def get_text(self):
        return self.text

    def __str__(self):
        # Format like textbound, but w/o ID or type
        return u'%d %d\t%s' % (self.start, self.end, self.text)

# Note search matches need to combine aspects of the note with aspects
# of the annotation it's attached to, so we'll represent such matches
# with this separate class.
class NoteMatch(object):
    """
    Represents a note (comment) matching a query.
    """
    def __init__(self, note, ann, start=0, end=0):
        self.note  = note
        self.ann   = ann
        self.start = start
        self.end   = end

        # for format_results
        self.text  = note.get_text()
        try:
            self.type  = ann.type
        except AttributeError:
            # nevermind
            pass

    def first_start(self):
        return self.start

    def last_end(self):
        return self.end

    def reference_id(self):
        # return reference to annotation that the note is attached to
        # (not the note itself)
        return self.ann.reference_id()

    def reference_text(self):
        # as above
        return self.ann.reference_text()

    def get_text(self):
        return self.note.get_text()

    def __str__(self):
        assert False, "INTERNAL ERROR: not implemented"

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
            # remove suffixes for Annotations to prompt parsing of all
            # annotation files.
            nosuff_fn = fn.replace(".ann","").replace(".a1","").replace(".a2","").replace(".rel","")
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

def __document_to_annotations(directory, document):
    """
    Given a directory and a document, returns an Annotations object
    for the file.
    """
    # TODO: put this shared functionality in a more reasonable place
    from document import real_directory
    from os.path import join as path_join

    real_dir = real_directory(directory)
    filenames = [path_join(real_dir, document)]

    return __filenames_to_annotations(filenames)

def __doc_or_dir_to_annotations(directory, document, scope):
    """
    Given a directory, a document, and a scope specification
    with the value "collection" or "document" selecting between
    the two, returns Annotations object for either the specific
    document identified (scope=="document") or all documents in
    the given directory (scope=="collection").
    """

    # TODO: lots of magic values here; try to avoid this

    if scope == "collection":
        return __directory_to_annotations(directory)
    elif scope == "document":
        # NOTE: "/NO-DOCUMENT/" is a workaround for a brat
        # client-server comm issue (issue #513).
        if document == "" or document == "/NO-DOCUMENT/":
            Messager.warning('No document selected for search in document.')
            return []
        else:
            return __document_to_annotations(directory, document)
    else:
        Messager.error('Unrecognized search scope specification %s' % scope)
        return []

def _get_text_type_ann_map(ann_objs, restrict_types=None, ignore_types=None, nested_types=None):
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
            if restrict_types != [] and t.type not in restrict_types:
                continue

            if t.text not in text_type_ann_map:
                text_type_ann_map[t.text] = {}
            if t.type not in text_type_ann_map[t.text]:
                text_type_ann_map[t.text][t.type] = []
            text_type_ann_map[t.text][t.type].append((ann_obj,t))

    return text_type_ann_map

def _get_offset_ann_map(ann_objs, restrict_types=None, ignore_types=None):
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

            for t_start, t_end in t.spans:
                for o in range(t_start, t_end):
                    if o not in offset_ann_map:
                        offset_ann_map[o] = set()
                    offset_ann_map[o].add(t)

    return offset_ann_map

def eq_text_neq_type_spans(ann_objs, restrict_types=None, ignore_types=None, nested_types=None):
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
    from ssplit import regex_sentence_boundary_gen

    m = {} # TODO: why is this a dict and not an array?
    sprev, snum = 0, 1 # note: sentences indexed from 1
    for sstart, send in regex_sentence_boundary_gen(s):
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
    from ssplit import regex_sentence_boundary_gen
    from tokenise import gtb_token_boundary_gen

    tokens = []

    sprev = 0
    for sstart, send in regex_sentence_boundary_gen(s):
        if sprev != sstart:
            # between-sentence space
            tokens.append(s[sprev:sstart])
        stext = s[sstart:send]
        tprev, tend = 0, 0
        for tstart, tend in gtb_token_boundary_gen(stext):
            if tprev != tstart:
                # between-token space
                tokens.append(s[sstart+tprev:sstart+tstart])
            tokens.append(s[sstart+tstart:sstart+tend])
            tprev = tend

        if tend != len(stext):
            # sentence-final space
            tokens.append(stext[tend:])

        sprev = send

    if sprev != len(s):
        # document-final space
        tokens.append(s[sprev:])

    assert "".join(tokens) == s, "INTERNAL ERROR\n'%s'\n'%s'" % ("".join(tokens),s)

    return tokens

def _split_tokens_more(tokens):
    """
    Search-specific extra tokenization.
    More aggressive than the general visualization-oriented tokenization.
    """
    pre_nonalnum_RE = re.compile(r'^(\W+)(.+)$', flags=DEFAULT_RE_FLAGS)
    post_nonalnum_RE = re.compile(r'^(.+?)(\W+)$', flags=DEFAULT_RE_FLAGS)

    new_tokens = []
    for t in tokens:
        m = pre_nonalnum_RE.match(t)
        if m:
            pre, t = m.groups()
            new_tokens.append(pre)
        m = post_nonalnum_RE.match(t)
        if m:
            t, post = m.groups()
            new_tokens.append(t)
            new_tokens.append(post)
        else:
            new_tokens.append(t)

    # sanity
    assert ''.join(tokens) == ''.join(new_tokens), "INTERNAL ERROR"
    return new_tokens
        
def eq_text_partially_marked(ann_objs, restrict_types=None, ignore_types=None, nested_types=None):
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

    max_length_tagged = max([len(s) for s in text_type_ann_map]+[0])

    # TODO: faster and less hacky way to detect missing annotations
    text_untagged_map = {}
    for ann_obj in ann_objs:
        doctext = ann_obj.get_document_text()

        # TODO: proper tokenization.
        # NOTE: this will include space.
        #tokens = re.split(r'(\s+)', doctext)
        try:
            tokens = _split_and_tokenize(doctext)
            tokens = _split_tokens_more(tokens)
        except:
            # TODO: proper error handling
            print >> sys.stderr, "ERROR: failed tokenization in %s, skipping" % ann_obj._input_files[0]
            continue

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

        for type_ in text_type_ann_map[text]:
            for ann_obj, ann in text_type_ann_map[text][type_]:
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
            print "(note: omitting %d instances of tagged '%s')" % (len(tagged)-cutoff_limit, text.encode('utf-8'))
        elif (len(untagged) > freq_ratio_cutoff * len(tagged) and
              len(untagged) > cutoff_limit):
            # cut off all but cutoff_limit from tagged
            for ann_obj, m in tagged:
                matches.add_match(ann_obj, m)
            for ann_obj, m in untagged[:cutoff_limit]:
                matches.add_match(ann_obj, m)
            print "(note: omitting %d instances of untagged '%s')" % (len(untagged)-cutoff_limit, text.encode('utf-8'))
        else:
            # include all
            for ann_obj, m in tagged + untagged:
                matches.add_match(ann_obj, m)
            
    
    return matches

def check_type_consistency(ann_objs, restrict_types=None, ignore_types=None, nested_types=None):
    """
    Searches for inconsistent types in given Annotations
    objects.  Returns a list of SearchMatchSet objects, one for each
    checked criterion that generated matches for the search.
    """

    match_sets = []

    m = eq_text_neq_type_spans(ann_objs, restrict_types=restrict_types, ignore_types=ignore_types, nested_types=nested_types)
    if len(m) != 0:
        match_sets.append(m)

    return match_sets


def check_missing_consistency(ann_objs, restrict_types=None, ignore_types=None, nested_types=None):
    """
    Searches for potentially missing annotations in given Annotations
    objects.  Returns a list of SearchMatchSet objects, one for each
    checked criterion that generated matches for the search.
    """

    match_sets = []

    m = eq_text_partially_marked(ann_objs, restrict_types=restrict_types, ignore_types=ignore_types, nested_types=nested_types)
    if len(m) != 0:
        match_sets.append(m)

    return match_sets

def _get_match_regex(text, text_match="word", match_case=False,
                     whole_string=False):
    """
    Helper for the various search_anns_for_ functions.
    """

    regex_flags = DEFAULT_RE_FLAGS
    if not match_case:
        regex_flags = regex_flags | re.IGNORECASE

    if text is None:
        text = ''
    # interpret special value standing in for empty string (#924)
    if text == DEFAULT_EMPTY_STRING:
        text = ''

    if text_match == "word":
        # full word match: require word boundaries or, optionally,
        # whole string boundaries
        if whole_string:
            return re.compile(r'^'+re.escape(text)+r'$', regex_flags)
        else:
            return re.compile(r'\b'+re.escape(text)+r'\b', regex_flags)
    elif text_match == "substring":
        # any substring match, as text (nonoverlapping matches)
        return re.compile(re.escape(text), regex_flags)
    elif text_match == "regex":
        try:
            return re.compile(text, regex_flags)
        except: # whatever (sre_constants.error, other?)
            Messager.warning('Given string "%s" is not a valid regular expression.' % text)
            return None        
    else:
        Messager.error('Unrecognized search match specification "%s"' % text_match)
        return None    

def search_anns_for_textbound(ann_objs, text, restrict_types=None, 
                              ignore_types=None, nested_types=None, 
                              text_match="word", match_case=False,
                              entities_only=False):
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

    # compile a regular expression according to arguments for matching
    match_regex = _get_match_regex(text, text_match, match_case)

    if match_regex is None:
        # something went wrong, return empty
        return matches

    for ann_obj in ann_objs:
        # collect per-document (ann_obj) for sorting
        ann_matches = []

        if entities_only:
            candidates = ann_obj.get_textbounds()
        else:
            candidates = ann_obj.get_entities()

        for t in candidates:
            if t.type in ignore_types:
                continue
            if restrict_types != [] and t.type not in restrict_types:
                continue
            if (text != None and text != "" and 
                text != DEFAULT_EMPTY_STRING and not match_regex.search(t.get_text())):
                continue
            if nested_types != []:
                # TODO: massively inefficient
                nested = [x for x in ann_obj.get_textbounds() 
                          if x != t and t.contains(x)]
                if len([x for x in nested if x.type in nested_types]) == 0:
                    continue

            ann_matches.append(t)

        # sort by start offset
        ann_matches.sort(lambda a,b: cmp((a.first_start(),-a.last_end()),
                                         (b.first_start(),-b.last_end())))

        # add to overall collection
        for t in ann_matches:
            matches.add_match(ann_obj, t)    

        # MAX_SEARCH_RESULT_NUMBER <= 0 --> no limit
        if len(matches) > MAX_SEARCH_RESULT_NUMBER and MAX_SEARCH_RESULT_NUMBER > 0:
            Messager.warning('Search result limit (%d) exceeded, stopping search.' % MAX_SEARCH_RESULT_NUMBER)
            break

    matches.limit_to(MAX_SEARCH_RESULT_NUMBER)

    # sort by document name for output
    matches.sort_matches()

    if REPORT_SEARCH_TIMINGS:
        process_delta = datetime.now() - process_start
        print >> stderr, "search_anns_for_textbound: processed in", str(process_delta.seconds)+"."+str(process_delta.microseconds/10000), "seconds"

    return matches

def search_anns_for_note(ann_objs, text, category,
                         restrict_types=None, ignore_types=None,
                         text_match="word", match_case=False):
    """
    Searches for the given text in the comment annotations in the
    given Annotations objects.  Returns a SearchMatchSet object.
    """

    global REPORT_SEARCH_TIMINGS
    if REPORT_SEARCH_TIMINGS:
        process_start = datetime.now()

    # treat None and empty list uniformly
    restrict_types = [] if restrict_types is None else restrict_types
    ignore_types   = [] if ignore_types is None else ignore_types

    if category is not None:
        description = "Comments on %s containing text '%s'" % (category, text)
    else:
        description = "Comments containing text '%s'" % text
    if restrict_types != []:
        description = description + ' (of type %s)' % (",".join(restrict_types))
    matches = SearchMatchSet(description)

    # compile a regular expression according to arguments for matching
    match_regex = _get_match_regex(text, text_match, match_case)

    if match_regex is None:
        # something went wrong, return empty
        return matches

    for ann_obj in ann_objs:
        # collect per-document (ann_obj) for sorting
        ann_matches = []

        candidates = ann_obj.get_oneline_comments()

        for n in candidates:
            a = ann_obj.get_ann_by_id(n.target)

            if a.type in ignore_types:
                continue
            if restrict_types != [] and a.type not in restrict_types:
                continue
            if (text != None and text != "" and 
                text != DEFAULT_EMPTY_STRING and not match_regex.search(n.get_text())):
                continue

            ann_matches.append(NoteMatch(n,a))

        ann_matches.sort(lambda a,b: cmp((a.first_start(),-a.last_end()),
                                         (b.first_start(),-b.last_end())))

        # add to overall collection
        for t in ann_matches:
            matches.add_match(ann_obj, t)    

        # MAX_SEARCH_RESULT_NUMBER <= 0 --> no limit
        if len(matches) > MAX_SEARCH_RESULT_NUMBER and MAX_SEARCH_RESULT_NUMBER > 0:
            Messager.warning('Search result limit (%d) exceeded, stopping search.' % MAX_SEARCH_RESULT_NUMBER)
            break

    matches.limit_to(MAX_SEARCH_RESULT_NUMBER)

    # sort by document name for output
    matches.sort_matches()

    if REPORT_SEARCH_TIMINGS:
        process_delta = datetime.now() - process_start
        print >> stderr, "search_anns_for_textbound: processed in", str(process_delta.seconds)+"."+str(process_delta.microseconds/10000), "seconds"

    return matches

def search_anns_for_relation(ann_objs, arg1, arg1type, arg2, arg2type, 
                             restrict_types=None, ignore_types=None, 
                             text_match="word", match_case=False):
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

    # compile regular expressions according to arguments for matching
    arg1_match_regex, arg2_match_regex = None, None
    if arg1 is not None:
        arg1_match_regex = _get_match_regex(arg1, text_match, match_case)
    if arg2 is not None:
        arg2_match_regex = _get_match_regex(arg2, text_match, match_case)

    if ((arg1 is not None and arg1_match_regex is None) or
        (arg2 is not None and arg2_match_regex is None)):
        # something went wrong, return empty
        return matches
    
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
                if arg1 is not None and not arg1_match_regex.search(arg1ent.get_text()):
                    continue
                if arg1type is not None and arg1type != arg1ent.type:
                    continue
            if arg2 is not None or arg2type is not None:
                arg2ent = ann_obj.get_ann_by_id(r.arg2)
                if arg2 is not None and not arg2_match_regex.search(arg2ent.get_text()):
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
            for arg, argtype, arg_match_regex in ((arg1, arg1type, arg1_match_regex), 
                                                  (arg2, arg2type, arg2_match_regex)):
                match_found = False
                for aeid in r.entities:
                    argent = ann_obj.get_ann_by_id(aeid)
                    if arg is not None and not arg_match_regex.search(argent.get_text()):
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

        # MAX_SEARCH_RESULT_NUMBER <= 0 --> no limit
        if len(matches) > MAX_SEARCH_RESULT_NUMBER and MAX_SEARCH_RESULT_NUMBER > 0:
            Messager.warning('Search result limit (%d) exceeded, stopping search.' % MAX_SEARCH_RESULT_NUMBER)
            break

    matches.limit_to(MAX_SEARCH_RESULT_NUMBER)

    # sort by document name for output
    matches.sort_matches()

    if REPORT_SEARCH_TIMINGS:
        process_delta = datetime.now() - process_start
        print >> stderr, "search_anns_for_relation: processed in", str(process_delta.seconds)+"."+str(process_delta.microseconds/10000), "seconds"

    return matches

def search_anns_for_event(ann_objs, trigger_text, args, 
                          restrict_types=None, ignore_types=None, 
                          text_match="word", match_case=False):
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

    # compile a regular expression according to arguments for matching
    if trigger_text is not None:
        trigger_match_regex = _get_match_regex(trigger_text, text_match, match_case)

        if trigger_match_regex is None:
            # something went wrong, return empty
            return matches
    
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
                not trigger_match_regex.search(t_ann.text)):
                continue

            # interpret unconstrained (all blank values) argument
            # "constraints" as no constraint
            arg_constraints = []
            for arg in args:
                if arg['role'] != '' or arg['type'] != '' or arg['text'] != '':
                    arg_constraints.append(arg)
            args = arg_constraints

            # argument constraints, if any
            if len(args) > 0:
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

                        if (arg['text'] is not None and arg['text'] != ''):
                            # TODO: it would be better to pre-compile regexs for
                            # all arguments with text constraints
                            match_regex = _get_match_regex(arg['text'], text_match, match_case)
                            if match_regex is None:
                                return matches
                            # TODO: there has to be a better way ...
                            if isinstance(arg_ent, annotation.EventAnnotation):
                                # compare against trigger text
                                text_ent = ann_obj.get_ann_by_id(ann_ent.trigger)
                            else:
                                # compare against entity text
                                text_ent = arg_ent
                            if not match_regex.search(text_ent.get_text()):
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
        ann_matches.sort(lambda a,b: cmp((a[0].first_start(),-a[0].last_end()),
                                         (b[0].first_start(),-b[0].last_end())))

        # add to overall collection
        for t_obj, e in ann_matches:
            matches.add_match(ann_obj, e)

        # MAX_SEARCH_RESULT_NUMBER <= 0 --> no limit
        if len(matches) > MAX_SEARCH_RESULT_NUMBER and MAX_SEARCH_RESULT_NUMBER > 0:
            Messager.warning('Search result limit (%d) exceeded, stopping search.' % MAX_SEARCH_RESULT_NUMBER)
            break

    matches.limit_to(MAX_SEARCH_RESULT_NUMBER)

    # sort by document name for output
    matches.sort_matches()

    if REPORT_SEARCH_TIMINGS:
        process_delta = datetime.now() - process_start
        print >> stderr, "search_anns_for_event: processed in", str(process_delta.seconds)+"."+str(process_delta.microseconds/10000), "seconds"

    return matches

def search_anns_for_text(ann_objs, text, 
                         restrict_types=None, ignore_types=None, nested_types=None, 
                         text_match="word", match_case=False):
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

    # compile a regular expression according to arguments for matching
    match_regex = _get_match_regex(text, text_match, match_case)

    if match_regex is None:
        # something went wrong, return empty
        return matches

    # main search loop
    for ann_obj in ann_objs:
        doctext = ann_obj.get_document_text()

        for m in match_regex.finditer(doctext):
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
                    if t.contains(m):
                        embedding.append(t)

            # Note interpretation of ignore_types here: if the text
            # span is embedded in one or more of the ignore_types or
            # the ignore_types include the special value "ANY", the
            # match is ignored.
            if len([e for e in embedding if e.type in ignore_types or "ANY" in ignore_types]) != 0:
                continue

            if restrict_types != [] and len([e for e in embedding if e.type in restrict_types]) == 0:
                continue

            # TODO: need a clean, standard way of identifying a text span
            # that does not involve an annotation; this is a bit of a hack
            tm = TextMatch(m.start(), m.end(), m.group())
            matches.add_match(ann_obj, tm)

        # MAX_SEARCH_RESULT_NUMBER <= 0 --> no limit
        if len(matches) > MAX_SEARCH_RESULT_NUMBER and MAX_SEARCH_RESULT_NUMBER > 0:
            Messager.warning('Search result limit (%d) exceeded, stopping search.' % MAX_SEARCH_RESULT_NUMBER)
            break

    matches.limit_to(MAX_SEARCH_RESULT_NUMBER)

    if REPORT_SEARCH_TIMINGS:
        process_delta = datetime.now() - process_start
        print >> stderr, "search_anns_for_text: processed in", str(process_delta.seconds)+"."+str(process_delta.microseconds/10000), "seconds"

    return matches

def format_results(matches, concordancing=False, context_length=50):
    """
    Given matches to a search (a SearchMatchSet), formats the results
    for the client, returning a dictionary with the results in the
    expected format.
    """
    # decided to give filename only, remove this bit if the decision
    # sticks
#     from document import relative_directory
    from os.path import basename

    # sanity
    if concordancing:
        try:
            context_length = int(context_length)
            assert context_length > 0, "format_results: invalid context length ('%s')" % str(context_length)
        except:
            # whatever goes wrong ...
            Messager.warning('Context length should be an integer larger than zero.')
            return {}            

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

    include_context = False
    if include_text and concordancing:
        include_context = True
        try:
            for ann_obj, ann in matches.get_matches():
                ann.first_start()
                ann.last_end()
        except AttributeError:
            include_context = False

    include_trigger_context = False
    if include_trigger_text and concordancing and not include_context:
        include_trigger_context = True
        try:
            for ann_obj, ann in matches.get_matches():
                trigger = ann_obj.get_ann_by_id(ann.trigger)
                trigger.first_start()
                trigger.last_end()
        except AttributeError:
            include_trigger_context = False

    # extend header fields in order of data fields
    if include_type:
        response['header'].append(('Type', 'string'))

    if include_context or include_trigger_context:
        # right-aligned string
        response['header'].append(('Left context', 'string-reverse'))

    if include_text:
        # center-align text when concordancing, default otherwise
        if include_context or include_trigger_context:
            response['header'].append(('Text', 'string-center'))
        else:
            response['header'].append(('Text', 'string'))

    if include_trigger_text:
        response['header'].append(('Trigger text', 'string'))

    if include_context or include_trigger_context:
        response['header'].append(('Right context', 'string'))

    # gather sets of reference IDs by document to highlight
    # all matches in a document at once
    matches_by_doc = {}
    for ann_obj, ann in matches.get_matches():
        docid = basename(ann_obj.get_document())

        if docid not in matches_by_doc:
            matches_by_doc[docid] = []

        matches_by_doc[docid].append(ann.reference_id())

    # fill in content
    items = []
    for ann_obj, ann in matches.get_matches():
        # First value ("a") signals that the item points to a specific
        # annotation, not a collection (directory) or document.
        # second entry is non-listed "pointer" to annotation
        docid = basename(ann_obj.get_document())

        # matches in the same doc other than the focus match
        other_matches = [rid for rid in matches_by_doc[docid] 
                         if rid != ann.reference_id()]

        items.append(["a", { 'matchfocus' : [ann.reference_id()],
                             'match' : other_matches,
                             }, 
                      docid, ann.reference_text()])

        if include_type:
            items[-1].append(ann.type)

        if include_context:
            context_ann = ann
        elif include_trigger_context:
            context_ann = ann_obj.get_ann_by_id(ann.trigger)
        else:
            context_ann = None

        if context_ann is not None:
            # left context
            start = max(context_ann.first_start() - context_length, 0)
            doctext = ann_obj.get_document_text()
            items[-1].append(doctext[start:context_ann.first_start()])

        if include_text:
            items[-1].append(ann.text)

        if include_trigger_text:
            try:
                items[-1].append(ann_obj.get_ann_by_id(ann.trigger).text)
            except:
                # TODO: specific exception
                items[-1].append("(ERROR)")

        if context_ann is not None:
            # right context
            end = min(context_ann.last_end() + context_length, 
                      len(ann_obj.get_document_text()))
            doctext = ann_obj.get_document_text()
            items[-1].append(doctext[context_ann.last_end():end])


    response['items'] = items
    return response

### brat interface functions ###

def _to_bool(s):
    """
    Given a string representing a boolean value sent over
    JSON, returns the corresponding actual boolean.
    """
    if s == "true":
        return True
    elif s == "false":
        return False
    else:
        assert False, "Error: '%s' is not a JSON boolean" % s

def search_text(collection, document, scope="collection",
                concordancing="false", context_length=50,
                text_match="word", match_case="false",
                text=""):

    directory = collection

    # Interpret JSON booleans
    concordancing = _to_bool(concordancing)
    match_case = _to_bool(match_case)

    ann_objs = __doc_or_dir_to_annotations(directory, document, scope)    

    matches = search_anns_for_text(ann_objs, text, 
                                   text_match=text_match, 
                                   match_case=match_case)
        
    results = format_results(matches, concordancing, context_length)
    results['collection'] = directory
    
    return results

def search_entity(collection, document, scope="collection",
                  concordancing="false", context_length=50,
                  text_match="word", match_case="false",
                  type=None, text=DEFAULT_EMPTY_STRING):

    directory = collection

    # Interpret JSON booleans
    concordancing = _to_bool(concordancing)
    match_case = _to_bool(match_case)

    ann_objs = __doc_or_dir_to_annotations(directory, document, scope)

    restrict_types = []
    if type is not None and type != "":
        restrict_types.append(type)

    matches = search_anns_for_textbound(ann_objs, text, 
                                        restrict_types=restrict_types, 
                                        text_match=text_match,
                                        match_case=match_case)
        
    results = format_results(matches, concordancing, context_length)
    results['collection'] = directory
    
    return results

def search_note(collection, document, scope="collection",
                concordancing="false", context_length=50,
                text_match="word", match_case="false",
                category=None, type=None, text=DEFAULT_EMPTY_STRING):

    directory = collection

    # Interpret JSON booleans
    concordancing = _to_bool(concordancing)
    match_case = _to_bool(match_case)

    ann_objs = __doc_or_dir_to_annotations(directory, document, scope)

    restrict_types = []
    if type is not None and type != "":
        restrict_types.append(type)

    matches = search_anns_for_note(ann_objs, text, category,
                                   restrict_types=restrict_types, 
                                   text_match=text_match,
                                   match_case=match_case)
        
    results = format_results(matches, concordancing, context_length)
    results['collection'] = directory
    
    return results

def search_event(collection, document, scope="collection",
                 concordancing="false", context_length=50,
                 text_match="word", match_case="false",
                 type=None, trigger=DEFAULT_EMPTY_STRING, args={}):

    directory = collection

    # Interpret JSON booleans
    concordancing = _to_bool(concordancing)
    match_case = _to_bool(match_case)

    ann_objs = __doc_or_dir_to_annotations(directory, document, scope)

    restrict_types = []
    if type is not None and type != "":
        restrict_types.append(type)

    # to get around lack of JSON object parsing in dispatcher, parse
    # args here. 
    # TODO: parse JSON in dispatcher; this is far from the right place to do this..
    from jsonwrap import loads
    args = loads(args)

    matches = search_anns_for_event(ann_objs, trigger, args, 
                                    restrict_types=restrict_types,
                                    text_match=text_match, 
                                    match_case=match_case)

    results = format_results(matches, concordancing, context_length)
    results['collection'] = directory
    
    return results

def search_relation(collection, document, scope="collection", 
                    concordancing="false", context_length=50,
                    text_match="word", match_case="false",
                    type=None, arg1=None, arg1type=None, 
                    arg2=None, arg2type=None):

    directory = collection

    # Interpret JSON booleans
    concordancing = _to_bool(concordancing)
    match_case = _to_bool(match_case)
    
    ann_objs = __doc_or_dir_to_annotations(directory, document, scope)

    restrict_types = []
    if type is not None and type != "":
        restrict_types.append(type)

    matches = search_anns_for_relation(ann_objs, arg1, arg1type,
                                       arg2, arg2type,
                                       restrict_types=restrict_types,
                                       text_match=text_match,
                                       match_case=match_case)

    results = format_results(matches, concordancing, context_length)
    results['collection'] = directory
    
    return results

### filename list interface functions (e.g. command line) ###

def search_files_for_text(filenames, text, restrict_types=None, ignore_types=None, nested_types=None):
    """
    Searches for the given text in the given set of files.
    """
    anns = __filenames_to_annotations(filenames)
    return search_anns_for_text(anns, text, restrict_types=restrict_types, ignore_types=ignore_types, nested_types=nested_types)

def search_files_for_textbound(filenames, text, restrict_types=None, ignore_types=None, nested_types=None, entities_only=False):
    """
    Searches for the given text in textbound annotations in the given
    set of files.
    """
    anns = __filenames_to_annotations(filenames)
    return search_anns_for_textbound(anns, text, restrict_types=restrict_types, ignore_types=ignore_types, nested_types=nested_types, entities_only=entities_only)

# TODO: filename list interface functions for event and relation search

def check_files_type_consistency(filenames, restrict_types=None, ignore_types=None, nested_types=None):
    """
    Searches for inconsistent annotations in the given set of files.
    """
    anns = __filenames_to_annotations(filenames)
    return check_type_consistency(anns, restrict_types=restrict_types, ignore_types=ignore_types, nested_types=nested_types)

def check_files_missing_consistency(filenames, restrict_types=None, ignore_types=None, nested_types=None):
    """
    Searches for potentially missing annotations in the given set of files.
    """
    anns = __filenames_to_annotations(filenames)
    return check_missing_consistency(anns, restrict_types=restrict_types, ignore_types=ignore_types, nested_types=nested_types)

def argparser():
    import argparse

    ap=argparse.ArgumentParser(description="Search BioNLP Shared Task annotations.")
    ap.add_argument("-v", "--verbose", default=False, action="store_true", help="Verbose output.")
    ap.add_argument("-ct", "--consistency-types", default=False, action="store_true", help="Search for inconsistently typed annotations.")
    ap.add_argument("-cm", "--consistency-missing", default=False, action="store_true", help="Search for potentially missing annotations.")
    ap.add_argument("-t", "--text", metavar="TEXT", help="Search for matching text.")
    ap.add_argument("-b", "--textbound", metavar="TEXT", help="Search for textbound matching text.")
    ap.add_argument("-e", "--entity", metavar="TEXT", help="Search for entity matching text.")
    ap.add_argument("-r", "--restrict", metavar="TYPE", nargs="+", help="Restrict to given types.")
    ap.add_argument("-i", "--ignore", metavar="TYPE", nargs="+", help="Ignore given types.")
    ap.add_argument("-n", "--nested", metavar="TYPE", nargs="+", help="Require type to be nested.")
    ap.add_argument("files", metavar="FILE", nargs="+", help="Files to verify.")
    return ap

def main(argv=None):
    import sys
    import os
    import urllib

    # ignore search result number limits on command-line invocations
    global MAX_SEARCH_RESULT_NUMBER
    MAX_SEARCH_RESULT_NUMBER = -1

    if argv is None:
        argv = sys.argv
    arg = argparser().parse_args(argv[1:])

    # TODO: allow multiple searches
    if arg.textbound is not None:
        matches = [search_files_for_textbound(arg.files, arg.textbound,
                                              restrict_types=arg.restrict,
                                              ignore_types=arg.ignore,
                                              nested_types=arg.nested)]
    elif arg.entity is not None:
        matches = [search_files_for_textbound(arg.files, arg.textbound,
                                              restrict_types=arg.restrict,
                                              ignore_types=arg.ignore,
                                              nested_types=arg.nested,
                                              entities_only=True)]
    elif arg.text is not None:
        matches = [search_files_for_text(arg.files, arg.text,
                                         restrict_types=arg.restrict,
                                         ignore_types=arg.ignore,
                                         nested_types=arg.nested)]
    elif arg.consistency_types:
        matches = check_files_type_consistency(arg.files,
                                               restrict_types=arg.restrict,
                                               ignore_types=arg.ignore,
                                               nested_types=arg.nested)
    elif arg.consistency_missing:
        matches = check_files_missing_consistency(arg.files,
                                                  restrict_types=arg.restrict,
                                                  ignore_types=arg.ignore,
                                                  nested_types=arg.nested)
    else:
        print >> sys.stderr, "Please specify action (-h for help)"
        return 1

    # guessing at the likely URL
    import getpass
    username = getpass.getuser()

    for m in matches:
        print m.criterion
        for ann_obj, ann in m.get_matches():
            # TODO: get rid of specific URL hack and similar
            baseurl='http://127.0.0.1/~%s/brat/#/' % username
            # sorry about this
            if isinstance(ann, TextMatch):
                annp = "%s~%s" % (ann.reference_id()[0], ann.reference_id()[1])
            else:
                annp = ann.reference_id()[0]
            anns = unicode(ann).rstrip()
            annloc = ann_obj.get_document().replace("data/","")
            outs = u"\t%s%s?focus=%s (%s)" % (baseurl, annloc, annp, anns)
            print outs.encode('utf-8')

if __name__ == "__main__":
    import sys

    # on command-line invocations, don't limit the number of results
    # as the user has direct control over the system.
    MAX_SEARCH_RESULT_NUMBER = -1

    sys.exit(main(sys.argv))
