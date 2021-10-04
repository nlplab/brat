#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:


# Programmatic usage
#
# # TextAnnotations(
# #     document=None,    # document path without extension
# #                       #   if None, the document will not be read or saved
# #     text=None,        # provides the text instead of loading from `.txt` file
# #     read_only=False,  # if True, the document will not be saved
# #     lock_dir=None,    # lock file directory (system tmp dir if None)
# #     source=None)      # provides the annotations instead of loading from `.ann` file
#
# # TextBoundAnnotationWithText(
# #     spans,            # list of (start, end) pairs
# #     id,               # ID like "T1"; can get new id with `get_new_id`
# #     type,             # label
# #     text,             # the text or the `TextAnnotations` object
# #                       #   if the latter, annotation automatically added to it
# #     text_tail="",
# #     source_id=None)
# #
# # .get_events()
# # .get_attributes()
# # .get_equivs()
# # .get_textbounds()
# # .get_relations()
# # .get_normalizations()
# # .get_entities()
# # .get_oneline_comments()
# # .get_statuses()
# # .get_triggers()
# # .add_annotation(ann)
# # .del_annotation(ann)
# # .get_ann_by_id(id)
# # .get_new_id(prefix, suffix=None)
# # .get_document_text()
# # .save(document=None)
# # .get_messages()
# #   .ok
# #   .errors
# #   .warnings
#
# # Available annotations:
# #
# # Annotation(tail)
# #   .get_deps()
# #   UnknownAnnotation(line)
# #   UnparsedIdedAnnotation(id, line)
# #   TypedAnnotation(type, tail)
# #     IdedAnnotation(id, type, tail)
# #       .reference_id()
# #       .reference_text()
# #       EventAnnotation(trigger, args, id, type, tail)
# #         .add_argument(role, argid)
# #       AttributeAnnotation(target, id, type, tail, value)
# #       NormalizationAnnotation(id, type, target, refdb, refid, tail)
# #       OnelineCommentAnnotation(target, id, type, tail)
# #         .get_text()
# #       TextBoundAnnotation(spans, id, type, tail)
# #         .first_start()
# #         .last_end()
# #         .get_text()
# #         .same_span(other)
# #         .contains(other)
# #         TextBoundAnnotationWithText(spans, id, type, text, text_tail)
# #       BinaryRelationAnnotation(id, type, arg1l, arg1, arg2l, arg2, tail)
# #     EquivAnnotation(type, entities, tail)
# #       .reference_id()
# #       .reference_text()
#
# doc1_path = "./brat_read"
# doc2_path = "./brat_write"
# doc3_path = "./brat_manual"
# doc4_path = "./brat_saveas"
#
# from annotation import TextAnnotations, TextBoundAnnotationWithText
#
# # Read `.ann` and `.txt` (and don't save)
# # (Strictly speaking, `read_only=True` is not necessary,
# # the annotations are only written to disk at context exit,
# # or with `.save` - no `with` or `.save`, no write)
# doc = TextAnnotations(doc1_path, read_only=True)
# for ann in doc.get_textbounds():
#     print(ann.id, ann.spans, ann.type, ann.text)
#
# # Create from scratch (and save `.ann` file)
# # (This class doesn't save text. If needed, save it yourself.)
# text = "To boldly go where no one has gone before"
# with TextAnnotations(doc2_path, text=text) as doc:
#     ann = TextBoundAnnotationWithText([[3, 9]], "T1", "Adverb", "boldly")
#     doc.add_annotation(ann)
#     # Alternately, you can just pass the `TextAnnotations` object instead of text
#     # this will automatically extract the text, and also add the annotation
#     # Also note that you can generate a new ID using `get_new_id`, if you want
#     id = doc.get_new_id("T")
#     TextBoundAnnotationWithText([[0, 2], [10, 12]], id, "Verb", doc)
#
# # Create from scratch entirely in-memory; get data as strings
# doc = TextAnnotations(text=text)
# TextBoundAnnotationWithText([[3, 9]], "T1", "Adverb", doc)
# TextBoundAnnotationWithText([[0, 2], [10, 12]], "T2", "Verb", doc)
# txt_file = open(doc3_path + ".txt", "tw", encoding="utf-8")
# ann_file = open(doc3_path + ".ann", "tw", encoding="utf-8")
# with txt_file, ann_file:
#     txt_file.write(text)
#     ann_file.write(str(doc))
#
# # Read one file, modify it, save as a different file
# # Not using `with` so the original file is not modified
# doc = TextAnnotations(doc2_path)
# ann = doc.get_ann_by_id("T1")
# doc.del_annotation(ann)
# doc.save(ann)


from __future__ import with_statement

from codecs import open as codecs_open
from itertools import chain, takewhile
from os import close as os_close
from os import access, W_OK
from os.path import join as path_join
from os.path import splitext, dirname, isfile, isdir, exists
from re import compile as re_compile
from re import match as re_match
from time import time


try:
    from common import ProtocolError
    from message import Messager
    from common import WORK_DIR
    try:
        from filelock import FileLock
    except:
        raise Exception("Please install `filelock` module")
    PROGRAMMATIC = False
except (ModuleNotFoundError, ImportError):
    PROGRAMMATIC = True
    ProtocolError = Exception

    import contextlib
    class MessageCollection:
        def __init__(self):
            self.ok = True
            self.errors = []
            self.warnings = []

    class MessageCollector(object):
        def __init__(self):
            self.messages = MessageCollection()

        def error(self, message, timeout=None):
            self.messages.ok = False
            self.messages.errors.append(message)

        def warning(self, message, timeout=None):
            self.messages.warnings.append(message)


'''
Functionality related to the annotation file format.

Author:     Pontus Stenetorp   <pontus is s u-tokyo ac jp>
Version:    2011-01-25
'''




# Constants
# The only suffix we allow to write to, which is the joined annotation file
JOINED_ANN_FILE_SUFF = 'ann'
# These file suffixes indicate partial annotations that can not be written to
# since they depend on multiple files for completeness
PARTIAL_ANN_FILE_SUFF = ['a1', 'a2', 'co', 'rel']
KNOWN_FILE_SUFF = [JOINED_ANN_FILE_SUFF] + PARTIAL_ANN_FILE_SUFF
TEXT_FILE_SUFFIX = 'txt'
# String used to catenate texts of discontinuous annotations in reference text
DISCONT_SEP = ' '
###

# If True, use BioNLP Shared Task 2013 compatibilty mode, allowing
# normalization annotations to be parsed using the BioNLP Shared Task
# 2013 format in addition to the brat format and allowing relations to
# reference event triggers. NOTE: Alternate format supported only for
# reading normalization annotations, not for creating new ones. Don't
# change this setting unless you are sure you know what you are doing.
BIONLP_ST_2013_COMPATIBILITY = True
BIONLP_ST_2013_NORMALIZATION_RES = [
    (re_compile(r'^(Reference) Annotation:(\S+) Referent:(\S+)'), r'\1 \2 \3'),
    (re_compile(r'^(Reference) Referent:(\S+) Annotation:(\S+)'), r'\1 \3 \2'),
]


class AnnotationLineSyntaxError(Exception):
    def __init__(self, line, line_num, filepath):
        self.line = line
        self.line_num = line_num
        self.filepath = filepath

    def __str__(self):
        u'Syntax error on line %d: "%s"' % (self.line_num, self.line)


class IdedAnnotationLineSyntaxError(AnnotationLineSyntaxError):
    def __init__(self, id, line, line_num, filepath):
        AnnotationLineSyntaxError.__init__(self, line, line_num, filepath)
        self.id = id

    def __str__(self):
        u'Syntax error on line %d (id %s): "%s"' % (
            self.line_num, self.id, self.line)


class AnnotationNotFoundError(Exception):
    def __init__(self, id):
        self.id = id

    def __str__(self):
        return u'Could not find an annotation with id: %s' % (self.id, )


class AnnotationError(ProtocolError):
    pass

class AnnotationFileNotFoundError(AnnotationError):
    def __init__(self, fn):
        self.fn = fn

    def __str__(self):
        return u'Could not find any annotations for %s' % (self.fn, )

    def json(self, json_dic):
        json_dic['exception'] = 'annotationFileNotFound'
        return json_dic


class AnnotationCollectionNotFoundError(AnnotationError):
    def __init__(self, cn):
        self.cn = cn

    def __str__(self):
        return u'Error accessing collection %s' % (self.cn, )

    def json(self, json_dic):
        # TODO: more specific error?
        json_dic['exception'] = 'annotationCollectionNotFound'
        return json_dic


class EventWithoutTriggerError(AnnotationError):
    def __init__(self, event):
        self.event = event

    def __str__(self):
        return u'Event "%s" lacks a trigger' % (self.event, )

    def json(self, json_dic):
        json_dic['exception'] = 'eventWithoutTrigger'
        return json_dic


class EventWithNonTriggerError(AnnotationError):
    def __init__(self, event, non_trigger):
        self.event = event
        self.non_trigger = non_trigger

    def __str__(self):
        return u'Non-trigger "%s" used by "%s" as trigger' % (
            self.non_trigger, self.event, )

    def json(self, json_dic):
        json_dic['exception'] = 'eventWithNonTrigger'
        return json_dic


class TriggerReferenceError(AnnotationError):
    def __init__(self, trigger, referencer):
        self.trigger = trigger
        self.referencer = referencer

    def __str__(self):
        return u'Trigger "%s" referenced by non-event "%s"' % (
            self.trigger, self.referencer, )

    def json(self, json_dic):
        json_dic['exception'] = 'triggerReference'
        return json_dic


class AnnotationTextFileNotFoundError(AnnotationFileNotFoundError):
    def __str__(self):
        return u'Could not read text file for %s' % (self.fn, )


class AnnotationsIsReadOnlyError(AnnotationError):
    def __init__(self, fn):
        self.fn = fn

    def __str__(self):
        # No extra message; the client is doing a fine job of reporting this
        # return u'Annotations read-only for %s' % (self.fn, )
        return ''

    def json(self, json_dic):
        json_dic['exception'] = 'annotationIsReadOnly'
        return json_dic


class DuplicateAnnotationIdError(AnnotationLineSyntaxError):
    def __init__(self, id, line, line_num, filepath):
        AnnotationLineSyntaxError.__init__(self, line, line_num, filepath)
        self.id = id

    def __str__(self):
        return (u'Duplicate id: %s on line %d (id %s): "%s"'
                ) % (self.id, self.line_num, self.id, self.line)


class InvalidIdError(Exception):
    def __init__(self, id):
        self.id = id

    def __str__(self):
        return u'Invalid id: %s' % (self.id, )


class DependingAnnotationDeleteError(Exception):
    def __init__(self, target, dependants):
        self.target = target
        self.dependants = dependants

    def __str__(self):
        return u'%s can not be deleted due to depending annotations %s' % (str(
            self.target).rstrip(), ",".join([str(d).rstrip() for d in self.dependants]))

    def html_error_str(self, response=None):
        return u'''Annotation:
        %s
        Has depending annotations attached to it:
        %s''' % (str(self.target).rstrip(), ",".join([str(d).rstrip() for d in self.dependants]))


class SpanOffsetOverlapError(AnnotationError):
    def __init__(self, offsets):
        self.offsets = offsets

    def __str__(self):
        return u'The offsets [%s] overlap' % (
            ', '.join(str(e) for e in self.offsets))

    def json(self, json_dic):
        json_dic['exception'] = 'spanOffsetOverlapError'
        return json_dic


# Open function that enforces strict, utf-8, and universal newlines for reading
# TODO: Could have another wrapping layer raising an appropriate AnnotationError
def open_textfile(filename, mode='rU'):
    # enforce universal newline support ('U') in read modes
    if len(mode) != 0 and mode[0] == 'r' and 'U' not in mode:
        mode = mode + 'U'
    return codecs_open(filename, mode, encoding='utf8', errors='strict')


def __split_annotation_id(id):
    m = re_match(r'^([A-Za-z]+|#[A-Za-z]*)([0-9]+)(.*?)$', id)
    if m is None:
        raise InvalidIdError(id)
    pre, num_str, suf = m.groups()
    return pre, num_str, suf


def annotation_id_prefix(id):
    pre = ''.join(c for c in takewhile(lambda x: not x.isdigit(), id))
    if not pre:
        raise InvalidIdError(id)
    return pre


def annotation_id_number(id):
    return __split_annotation_id(id)[1]


def is_valid_id(id):
    # special case: '*' is acceptable as an "ID"
    if id == '*':
        return True

    try:
        # currently accepting any ID that can be split.
        # TODO: consider further constraints
        __split_annotation_id(id)[1]
        return True
    except InvalidIdError:
        return False


class Annotations(object):
    """Basic annotation storage.

    Not concerned with conformity of annotations to text; can be created
    without access to the text file to which the annotations apply.
    """

    def get_document(self):
        return self._document

    def _select_input_files(self, document):
        """Given a document name (path), returns a list of the names of
        specific annotation files relevant to the document, or the empty list
        if none found.

        For example, given "1000", may return ["1000.a1", "1000.a2"].
        May set self._read_only flag to True.
        """

        try:
            # Do we have a valid suffix? If so, it is probably best to the file
            suff = document[document.rindex('.') + 1:]
            if suff == JOINED_ANN_FILE_SUFF:
                # It is a joined file, let's load it
                input_files = [document]
            elif suff in PARTIAL_ANN_FILE_SUFF:
                # It is only a partial annotation, we will most likely fail
                # but we will try opening it
                input_files = [document]
                if not PROGRAMMATIC:
                    self._read_only = True
            else:
                input_files = []
        except ValueError:
            # The document lacked a suffix
            input_files = []

        if not input_files:
            # Our first attempts at finding the input by checking suffixes
            # failed, so we try to attach know suffixes to the path.
            sugg_path = document + '.' + JOINED_ANN_FILE_SUFF
            if isfile(sugg_path):
                # We found a joined file by adding the joined suffix
                input_files = [sugg_path]
            else:
                # Our last shot, we go for as many partial files as possible
                input_files = [sugg_path for sugg_path in
                               (document + '.' + suff
                                for suff in PARTIAL_ANN_FILE_SUFF)
                               if isfile(sugg_path)]
                if not PROGRAMMATIC:
                    self._read_only = True

        # Do we lack write permissions?
        # TODO: Should raise an exception or warning
        if not self._read_only:
            if not all(_writable(filename) for filename in input_files):
                self._read_only = True

        return input_files

    if PROGRAMMATIC:
        def get_messages(self):
            return self.messages.messages

    def _init_messager(self):
        if not hasattr(self, 'messager'):
            if PROGRAMMATIC:
                self.messages = MessageCollector()
            else:
                self.messages = Messager


    # TODO: DOC!
    def __init__(self, document=None, read_only=False, lock_dir=None, source=None):
        if lock_dir is None:
            if PROGRAMMATIC:
                from tempfile import gettempdir
                lock_dir = gettempdir()
            else:
                lock_dir = WORK_DIR

        self._init_messager()

        self.lock_dir = lock_dir

        # this decides which parsing function is invoked by annotation
        # ID prefix (first letter)
        self._parse_function_by_id_prefix = {
            'T': self._parse_textbound_annotation,
            'M': self._parse_modifier_annotation,
            'A': self._parse_attribute_annotation,
            'N': self._parse_normalization_annotation,
            'R': self._parse_relation_annotation,
            '*': self._parse_equiv_annotation,
            'E': self._parse_event_annotation,
            '#': self._parse_comment_annotation,
        }

        # TODO: DOC!
        # TODO: Incorparate file locking! Is the destructor called upon inter
        # crash?
        from collections import defaultdict
        from os.path import getctime, getmtime
        #from fileinput import FileInput, hook_encoded

        # we should remember this
        self._document = document

        self.failed_lines = []
        self.externally_referenced_triggers = set()

        # Here be dragons, these objects need constant updating and syncing
        # Annotation for each line of the file
        self._lines = []
        # Mapping between annotation objects and which line they occur on
        # Range: [0, inf.) unlike [1, inf.) which is common for files
        self._line_by_ann = {}
        # Maximum id number used for each id prefix, to speed up id generation
        # XXX: This is effectively broken by the introduction of id suffixes
        self._max_id_num_by_prefix = defaultdict(lambda: 1)
        # Annotation by id, not includid non-ided annotations
        self._ann_by_id = {}
        ###

        # We use some heuristics to find the appropriate annotation files
        self._read_only = read_only
        if document is not None:
            input_files = self._select_input_files(document)

            if not input_files:
                with open('{}.{}'.format(document, JOINED_ANN_FILE_SUFF), 'w'):
                    pass

                input_files = self._select_input_files(document)
                if not input_files and not PROGRAMMATIC:
                    raise AnnotationFileNotFoundError(document)

        else:
            input_files = None

        # We then try to open the files we got using the heuristics
        # self._file_input = FileInput(openhook=hook_encoded('utf-8'))
        self._input_files = input_files

        # Finally, parse the given annotation file
        self.ann_line_num = -1
        if input_files:
            self._parse_ann_file(input_files)
        elif source:
            self._parse_ann_lines(source.splitlines(keepends=True))

        # Sanity checking that can only be done post-parse
        self._sanity()
        # XXX: Hack to get the timestamps after parsing
        if (document is not None and
                len(self._input_files) == 1 and
                self._input_files[0].endswith(JOINED_ANN_FILE_SUFF)):
            self.ann_mtime = getmtime(self._input_files[0])
            self.ann_ctime = getctime(self._input_files[0])
        else:
            # We don't have a single file, just set to epoch for now
            self.ann_mtime = -1
            self.ann_ctime = -1

    def _sanity(self):
        # Beware, we ONLY do format checking, leave your semantics hat at home

        # Check that referenced IDs are defined
        for ann in self:
            for rid in chain(*ann.get_deps()):
                try:
                    self.get_ann_by_id(rid)
                except AnnotationNotFoundError:
                    # TODO: do more than just send a message for this error?
                    self.messages.error(
                        'ID ' +
                        rid +
                        ' not defined, referenced from annotation ' +
                        str(ann))

        # Check that each event has a trigger
        for e_ann in self.get_events():
            try:
                tr_ann = self.get_ann_by_id(e_ann.trigger)

                # If the annotation is not text-bound or of different type
                if (not isinstance(tr_ann, TextBoundAnnotation) or
                        tr_ann.type != e_ann.type):
                    raise EventWithNonTriggerError(e_ann, tr_ann)
            except AnnotationNotFoundError:
                raise EventWithoutTriggerError(e_ann)

        # Check that every trigger is only referenced by events

        # Create a map for non-event references
        referenced_to_referencer = {}
        for non_e_ann in (a for a in self
                          if not isinstance(a, EventAnnotation)
                          and isinstance(a, IdedAnnotation)):
            for ref in chain(*non_e_ann.get_deps()):
                try:
                    referenced_to_referencer[ref].add(non_e_ann.id)
                except KeyError:
                    referenced_to_referencer[ref] = set((non_e_ann.id, ))

        # Ensure that no non-event references a trigger
        for tr_ann in self.get_triggers():
            if tr_ann.id in referenced_to_referencer:
                conflict_ann_ids = referenced_to_referencer[tr_ann.id]
                if BIONLP_ST_2013_COMPATIBILITY:
                    # Special-case processing for BioNLP ST 2013: allow
                    # Relations to reference event triggers (#926).
                    remaining_confict_ann_ids = set()
                    for rid in conflict_ann_ids:
                        referencer = self.get_ann_by_id(rid)
                        if not isinstance(
                                referencer, BinaryRelationAnnotation):
                            remaining_confict_ann_ids.add(rid)
                        else:
                            self.externally_referenced_triggers.add(tr_ann.id)
                    conflict_ann_ids = remaining_confict_ann_ids
                # Note: Only reporting one of the conflicts (TODO)
                if conflict_ann_ids:
                    referencer = self.get_ann_by_id(list(conflict_ann_ids)[0])
                    raise TriggerReferenceError(tr_ann, referencer)

    def get_events(self):
        return (a for a in self if isinstance(a, EventAnnotation))

    def get_attributes(self):
        return (a for a in self if isinstance(a, AttributeAnnotation))

    def get_equivs(self):
        return (a for a in self if isinstance(a, EquivAnnotation))

    def get_textbounds(self):
        return (a for a in self if isinstance(a, TextBoundAnnotation))

    def get_relations(self):
        return (a for a in self if isinstance(a, BinaryRelationAnnotation))

    def get_normalizations(self):
        return (a for a in self if isinstance(a, NormalizationAnnotation))

    def get_entities(self):
        # Entities are textbounds that are not triggers
        triggers = [t for t in self.get_triggers()]
        return (a for a in self if (isinstance(a, TextBoundAnnotation) and
                                    a not in triggers))

    def get_oneline_comments(self):
        # XXX: The status exception is for the document status protocol
        #       which is yet to be formalised
        return (a for a in self if isinstance(a, OnelineCommentAnnotation)
                and a.type != 'STATUS')

    def get_statuses(self):
        return (a for a in self if isinstance(a, OnelineCommentAnnotation)
                and a.type == 'STATUS')

    def get_triggers(self):
        # Triggers are text-bounds referenced by events
        # TODO: this omits entity triggers that lack a referencing event
        # (for one reason or another -- brat shouldn't define any.)
        return (self.get_ann_by_id(e.trigger) for e in self.get_events())

    # TODO: getters for other categories of annotations
    # TODO: Remove read and use an internal and external version instead
    def add_annotation(self, ann, read=False):
        # log_info(u'Will add: ' + str(ann).rstrip('\n') + ' ' + str(type(ann)))
        # TODO: DOC!
        # TODO: Check read only
        if not read and self._read_only:
            raise AnnotationsIsReadOnlyError(self.get_document())

        # Equivs have to be merged with other equivs
        try:
            # Bail as soon as possible for non-equivs
            ann.entities  # TODO: what is this?
            merge_cand = ann
            for eq_ann in self.get_equivs():
                try:
                    # Make sure that this Equiv duck quacks
                    eq_ann.entities
                except AttributeError as e:
                    assert False, 'got a non-entity from an entity call'

                # Do we have an entitiy in common with this equiv?
                for ent in merge_cand.entities:
                    if ent in eq_ann.entities:
                        for m_ent in merge_cand.entities:
                            if m_ent not in eq_ann.entities:
                                eq_ann.entities.append(m_ent)
                        # Don't try to delete ann since it never was added
                        if merge_cand != ann:
                            try:
                                self.del_annotation(merge_cand)
                            except DependingAnnotationDeleteError:
                                assert False, ('Equivs lack ids and should '
                                               'never have dependent annotations')
                        merge_cand = eq_ann
                        # We already merged it all, break to the next ann
                        break

            if merge_cand != ann:
                # The proposed annotation was simply merged, no need to add it
                # Update the modification time
                from time import time
                self.ann_mtime = time()
                return

        except AttributeError:
            # XXX: This can catch a ton more than we want to! Ugly!
            # It was not an Equiv, skip along
            pass

        # Register the object id
        try:
            self._ann_by_id[ann.id] = ann
            pre, num = annotation_id_prefix(
                ann.id), annotation_id_number(
                ann.id)
            self._max_id_num_by_prefix[pre] = max(
                int(num), int(self._max_id_num_by_prefix[pre]))
        except AttributeError:
            # The annotation simply lacked an id which is fine
            pass

        # Add the annotation as the last line
        self._lines.append(ann)
        self._line_by_ann[ann] = len(self) - 1
        # Update the modification time
        from time import time
        self.ann_mtime = time()

    def del_annotation(self, ann, tracker=None):
        # TODO: Check read only
        # TODO: Flag to allow recursion
        # TODO: Sampo wants to allow delet of direct deps but not indirect, one step
        # TODO: needed to pass tracker to track recursive mods, but use is too
        #      invasive (direct modification of ModificationTracker.deleted)
        # TODO: DOC!
        if self._read_only:
            raise AnnotationsIsReadOnlyError(self.get_document())

        try:
            ann.id
        except AttributeError:
            # If it doesn't have an id, nothing can depend on it
            if tracker is not None:
                tracker.deletion(ann)
            self._atomic_del_annotation(ann)
            # Update the modification time
            from time import time
            self.ann_mtime = time()
            return

        # collect annotations dependending on ann
        ann_deps = []

        for other_ann in self:
            soft_deps, hard_deps = other_ann.get_deps()
            if str(ann.id) in soft_deps | hard_deps:
                ann_deps.append(other_ann)

        # If all depending are AttributeAnnotations or EquivAnnotations,
        # delete all modifiers recursively (without confirmation) and remove
        # the annotation id from the equivs (and remove the equiv if there is
        # only one id left in the equiv)
        # Note: this assumes AttributeAnnotations cannot have
        # other dependencies depending on them, nor can EquivAnnotations
        if all((False for d in ann_deps if (
            not isinstance(d, AttributeAnnotation)
            and not isinstance(d, EquivAnnotation)
            and not isinstance(d, OnelineCommentAnnotation)
            and not isinstance(d, NormalizationAnnotation)
        ))):

            for d in ann_deps:
                if isinstance(d, AttributeAnnotation):
                    if tracker is not None:
                        tracker.deletion(d)
                    self._atomic_del_annotation(d)
                elif isinstance(d, EquivAnnotation):
                    if len(d.entities) <= 2:
                        # An equiv has to have more than one member
                        self._atomic_del_annotation(d)
                        if tracker is not None:
                            tracker.deletion(d)
                    else:
                        if tracker is not None:
                            before = str(d)
                        d.entities.remove(str(ann.id))
                        if tracker is not None:
                            tracker.change(before, d)
                elif isinstance(d, OnelineCommentAnnotation):
                    # TODO: Can't anything refer to comments?
                    self._atomic_del_annotation(d)
                    if tracker is not None:
                        tracker.deletion(d)
                elif isinstance(d, NormalizationAnnotation):
                    # Nothing should be able to reference normalizations
                    self._atomic_del_annotation(d)
                    if tracker is not None:
                        tracker.deletion(d)
                else:
                    # all types we allow to be deleted along with
                    # annotations they depend on should have been
                    # covered above.
                    assert False, "INTERNAL ERROR"
            ann_deps = []

        if ann_deps:
            raise DependingAnnotationDeleteError(ann, ann_deps)

        if tracker is not None:
            tracker.deletion(ann)
        self._atomic_del_annotation(ann)

    def _atomic_del_annotation(self, ann):
        # TODO: DOC
        # Erase the ann by id shorthand
        try:
            del self._ann_by_id[ann.id]
        except AttributeError:
            # So, we did not have id to erase in the first place
            pass

        ann_line = self._line_by_ann[ann]
        # Erase the main annotation
        del self._lines[ann_line]
        # Erase the ann by line shorthand
        del self._line_by_ann[ann]
        # Update the line shorthand of every annotation after this one
        # to reflect the new self._lines
        for l_num in range(ann_line, len(self)):
            self._line_by_ann[self[l_num]] = l_num
        # Update the modification time
        from time import time
        self.ann_mtime = time()

    def get_ann_by_id(self, id):
        # TODO: DOC
        try:
            return self._ann_by_id[id]
        except KeyError:
            raise AnnotationNotFoundError(id)

    def get_new_id(self, prefix, suffix=None):
        """Return a new valid unique id for this annotation file for the given
        prefix. No ids are re-used for traceability over time for annotations,
        but this only holds for the lifetime of the annotation object. If the
        annotation file is parsed once again into an annotation object the next
        assigned id will be the maximum seen for a given prefix plus one which
        could have been deleted during a previous annotation session.

        Warning: get_new_id('T') == get_new_id('T')
        Just calling this method does not reserve the id, you need to
        add the annotation with the returned id to the annotation object in
        order to reserve it.

        Argument(s):
        id_pre - an annotation prefix on the format [A-Za-z]+

        Returns:
        An id that is guaranteed to be unique for the lifetime of the
        annotation.
        """
        # XXX: We have changed this one radically!
        # XXX: Stupid and linear
        if suffix is None:
            suffix = ''
        # XXX: Arbitrary constant!
        for suggestion in (
            prefix +
            str(i) +
            suffix for i in range(
                1,
                2**15)):
            # This is getting more complicated by the minute, two checks since
            # the developers no longer know when it is an id or string.
            if suggestion not in self._ann_by_id:
                return suggestion

    # XXX: This syntax is subject to change
    def _parse_attribute_annotation(
            self, id, data, data_tail, input_file_path):
        match = re_match(r'(.+?) (.+?) (.+?)$', data)
        if match is None:
            # Is it an old format without value?
            match = re_match(r'(.+?) (.+?)$', data)

            if match is None:
                raise IdedAnnotationLineSyntaxError(
                    id, self.ann_line, self.ann_line_num + 1, input_file_path)

            _type, target = match.groups()
            value = True
        else:
            _type, target, value = match.groups()

        # Verify that the ID is indeed valid
        try:
            annotation_id_number(target)
        except InvalidIdError:
            raise IdedAnnotationLineSyntaxError(
                id, self.ann_line, self.ann_line_num + 1, input_file_path)

        return AttributeAnnotation(
            target, id, _type, '', value, source_id=input_file_path)

    def _parse_event_annotation(self, id, data, data_tail, input_file_path):
        # XXX: A bit nasty, we require a single space
        try:
            type_delim = data.index(' ')
            type_trigger, type_trigger_tail = (
                data[:type_delim], data[type_delim:])
        except ValueError:
            type_trigger = data.rstrip('\r\n')
            type_trigger_tail = None

        try:
            type, trigger = type_trigger.split(':')
        except ValueError:
            # TODO: consider accepting events without triggers, e.g.
            # BioNLP ST 2011 Bacteria task
            raise IdedAnnotationLineSyntaxError(
                id, self.ann_line, self.ann_line_num + 1, input_file_path)

        if type_trigger_tail is not None:
            args = [tuple(arg.split(':')) for arg in type_trigger_tail.split()]
        else:
            args = []

        return EventAnnotation(
            trigger,
            args,
            id,
            type,
            data_tail,
            source_id=input_file_path)

    def _parse_relation_annotation(self, id, data, data_tail, input_file_path):
        try:
            type_delim = data.index(' ')
            type, type_tail = (data[:type_delim], data[type_delim:])
        except ValueError:
            # cannot have a relation with just a type (contra event)
            raise IdedAnnotationLineSyntaxError(
                id, self.ann_line, self.ann_line_num + 1, input_file_path)

        try:
            args = [tuple(arg.split(':')) for arg in type_tail.split()]
        except ValueError:
            raise IdedAnnotationLineSyntaxError(
                id, self.ann_line, self.ann_line_num + 1, input_file_path)

        if len(args) != 2:
            self.messages.error(
                'Error parsing relation: must have exactly two arguments')
            raise IdedAnnotationLineSyntaxError(
                id, self.ann_line, self.ann_line_num + 1, input_file_path)

        if args[0][0] == args[1][0]:
            self.messages.error(
                'Error parsing relation: arguments must not be identical')
            raise IdedAnnotationLineSyntaxError(
                id, self.ann_line, self.ann_line_num + 1, input_file_path)

        return BinaryRelationAnnotation(id, type,
                                        args[0][0], args[0][1],
                                        args[1][0], args[1][1],
                                        data_tail, source_id=input_file_path)

    def _parse_equiv_annotation(self, dummy, data, data_tail, input_file_path):
        # NOTE: first dummy argument to have a uniform signature with other
        # parse_* functions
        # TODO: this will split on any space, which is likely not correct
        try:
            type, type_tail = data.split(None, 1)
        except ValueError:
            # no space: Equiv without arguments?
            raise AnnotationLineSyntaxError(
                self.ann_line, self.ann_line_num + 1, input_file_path)
        equivs = type_tail.split(None)
        return EquivAnnotation(type, equivs, data_tail,
                               source_id=input_file_path)

    # Parse an old modifier annotation for backwards compatibility
    def _parse_modifier_annotation(self, id, data, data_tail, input_file_path):
        type, target = data.split()
        return AttributeAnnotation(
            target,
            id,
            type,
            data_tail,
            True,
            source_id=input_file_path)

    def _split_textbound_data(self, id, data, input_file_path):
        try:
            # first space-separated string is type
            type, rest = data.split(' ', 1)

            # rest should be semicolon-separated list of "START END"
            # pairs, where START and END are integers
            spans = []
            for span_str in rest.split(';'):
                start_str, end_str = span_str.split(' ', 2)

                # ignore trailing whitespace
                end_str = end_str.rstrip()

                if any((c.isspace() for c in end_str)):
                    self.messages.error(
                        'Error parsing textbound "%s\t%s". (Using space instead of tab?)' %
                        (id, data))
                    raise IdedAnnotationLineSyntaxError(
                        id, self.ann_line, self.ann_line_num + 1, input_file_path)

                start, end = (int(start_str), int(end_str))
                spans.append((start, end))

        except BaseException:
            raise IdedAnnotationLineSyntaxError(
                id, self.ann_line, self.ann_line_num + 1, input_file_path)

        return type, spans

    def _parse_textbound_annotation(
            self, _id, data, data_tail, input_file_path):
        _type, spans = self._split_textbound_data(_id, data, input_file_path)
        return TextBoundAnnotation(
            spans, _id, _type, data_tail, source_id=input_file_path)

    def _parse_normalization_annotation(
            self, _id, data, data_tail, input_file_path):
        # special-case processing for BioNLP ST 2013 variant of
        # normalization format
        if BIONLP_ST_2013_COMPATIBILITY:
            for r, s in BIONLP_ST_2013_NORMALIZATION_RES:
                d = r.sub(s, data, count=1)
                if d != data:
                    data = d
                    break

        match = re_match(r'(\S+) (\S+) (\S+?):(\S+)', data)
        if match is None:
            raise IdedAnnotationLineSyntaxError(
                _id, self.ann_line, self.ann_line_num + 1, input_file_path)
        _type, target, refdb, refid = match.groups()

        return NormalizationAnnotation(
            _id,
            _type,
            target,
            refdb,
            refid,
            data_tail,
            source_id=input_file_path)

    def _parse_comment_annotation(self, _id, data, data_tail, input_file_path):
        try:
            _type, target = data.split()
        except ValueError:
            raise IdedAnnotationLineSyntaxError(
                _id, self.ann_line, self.ann_line_num + 1, input_file_path)
        return OnelineCommentAnnotation(
            target, _id, _type, data_tail, source_id=input_file_path)

    def _parse_ann_file(self, input_files):
        for input_file_path in input_files:
            with open_textfile(input_file_path) as input_file:
                ann_lines = input_file.readlines()
                self._parse_ann_lines(ann_lines, input_file_path)

    def _parse_ann_lines(self, ann_lines, input_file_path=None):
        # for self.ann_line_num, self.ann_line in
        # enumerate(self._file_input):
        for self.ann_line in ann_lines:
            self.ann_line_num += 1
            try:
                # ID processing
                try:
                    id, id_tail = self.ann_line.split('\t', 1)
                except ValueError:
                    raise AnnotationLineSyntaxError(
                        self.ann_line, self.ann_line_num + 1, input_file_path)

                pre = annotation_id_prefix(id)

                if id in self._ann_by_id and pre != '*':
                    raise DuplicateAnnotationIdError(
                        id, self.ann_line, self.ann_line_num + 1, input_file_path)

                # if the ID is not valid, need to fail with
                # AnnotationLineSyntaxError (not
                # IdedAnnotationLineSyntaxError).
                if not is_valid_id(id):
                    raise AnnotationLineSyntaxError(
                        self.ann_line, self.ann_line_num + 1, input_file_path)

                # Cases for lines
                try:
                    data_delim = id_tail.index('\t')
                    data, data_tail = (id_tail[:data_delim],
                                        id_tail[data_delim:])
                except ValueError:
                    data = id_tail
                    # No tail at all, although it should have a \t
                    data_tail = ''

                new_ann = None

                #log_info('Will evaluate prefix: ' + pre)

                assert len(pre) >= 1, "INTERNAL ERROR"
                pre_first = pre[0]

                try:
                    parse_func = self._parse_function_by_id_prefix[pre_first]
                    new_ann = parse_func(
                        id, data, data_tail, input_file_path)
                except KeyError:
                    raise IdedAnnotationLineSyntaxError(
                        id, self.ann_line, self.ann_line_num + 1, input_file_path)

                assert new_ann is not None, "INTERNAL ERROR"
                self.add_annotation(new_ann, read=True)
            except IdedAnnotationLineSyntaxError as e:
                # Could parse an ID but not the whole line; add
                # UnparsedIdedAnnotation
                self.add_annotation(
                    UnparsedIdedAnnotation(
                        e.id, e.line, source_id=e.filepath), read=True)
                self.failed_lines.append(e.line_num - 1)

            except AnnotationLineSyntaxError as e:
                # We could not parse even an ID on the line, just add
                # it as an unknown annotation
                self.add_annotation(
                    UnknownAnnotation(
                        e.line,
                        source_id=e.filepath),
                    read=True)
                # NOTE: For access we start at line 0, not 1 as in here
                self.failed_lines.append(e.line_num - 1)

    def __str__(self):
        s = u'\n'.join(str(ann).rstrip(u'\r\n') for ann in self)
        if not s:
            return u''
        else:
            return s if s[-1] == u'\n' else s + u'\n'

    def __it__(self):
        for ann in self._lines:
            yield ann

    def __getitem__(self, val):
        try:
            # First, try to use it as a slice object
            return self._lines[val.start, val.stop, val.step]
        except AttributeError:
            # It appears not to be a slice object, try it as an index
            return self._lines[val]

    def __len__(self):
        return len(self._lines)

    def __enter__(self):
        # No need to do any handling here, the constructor handles that
        return self

    def __exit__(self, type, value, traceback):
        # self._file_input.close()

        # is it even needed?
        if self._document is None:
            return

        if self._read_only:
            return

        self.save()

    def save(self, document=None):
        if document is None:
            document = self._document

            if document is None:
                raise Exception("No document path provided")

        if self._read_only:
            raise Exception("Cannot save, read only")

        assert len(self._input_files) == 1, 'more than one valid outfile'

        # We are hitting the disk a lot more than we should here, what we
        # should have is a modification flag in the object but we can't
        # due to how we change the annotations.

        out_str = str(self)
        with open_textfile(self._input_files[0], 'r') as old_ann_file:
            old_str = old_ann_file.read()

        # Was it changed?
        if out_str == old_str:
            # Then just return
            return

        # Protect the write so we don't corrupt the file
        if PROGRAMMATIC:
            lock_file = contextlib.suppress()
        else:
            lock_file = FileLock(path_join(
                    self.lock_dir, str(hash(self._input_files[0].replace('/', '_'))) + '.lock'
            ))
        with lock_file:
            #from tempfile import NamedTemporaryFile
            from tempfile import mkstemp
            # TODO: XXX: Is copyfile really atomic?
            from shutil import copyfile
            # XXX: NamedTemporaryFile only supports encoding for Python 3
            #       so we hack around it.
            # with NamedTemporaryFile('w', suffix='.ann') as tmp_file:
            # Grab the filename, but discard the handle
            tmp_fh, tmp_fname = mkstemp(suffix='.ann')
            os_close(tmp_fh)
            try:
                with open_textfile(tmp_fname, 'w') as tmp_file:
                    # XXX: Temporary hack to make sure we don't write corrupted
                    #       files, but the client will already have the version
                    #       at this stage leading to potential problems upon
                    #       the next change to the file.
                    tmp_file.write(out_str)
                    tmp_file.flush()

                    try:
                        # read only, because we write manually using copyfile; this prevents certain reentrant errors
                        with Annotations(tmp_file.name, read_only=True) as ann:
                            # Move the temporary file onto the old file
                            copyfile(tmp_file.name, self._input_files[0])
                            # As a matter of convention we adjust the modified
                            # time of the data dir when we write to it. This
                            # helps us to make back-ups
                            # time()
                            # XXX: Disabled for now!
                            #utime(DATA_DIR, (now, now))
                    except Exception as e:
                        self.messages.error(
                            'ERROR writing changes: generated annotations cannot be read back in!\n(This is almost certainly a system error, please contact the developers.)\n%s' %
                            e, -1)
                        raise
            finally:
                try:
                    from os import remove
                    remove(tmp_fname)
                except Exception as e:
                    self.messages.error(
                        "Error removing temporary file '%s'" %
                        tmp_fname)

    def __in__(self, other):
        # XXX: You should do this one!
        pass


class TextAnnotations(Annotations):
    """Text-bound annotation storage.

    Extends Annotations in assuming access to text text to which the
    annotations apply and verifying the correctness of text-bound
    annotations against the text.
    """

    def __init__(self, document=None, text=None, read_only=False, lock_dir=None, source=None):
        self._init_messager()

        # First read the text or the Annotations can't verify the annotations
        if document:
            if document.endswith('.txt'):
                textfile_path = document
            else:
                # Do we have a known extension?
                _, file_ext = splitext(document)
                if not file_ext or file_ext not in KNOWN_FILE_SUFF:
                    textfile_path = document
                else:
                    textfile_path = document[:len(document) - len(file_ext)]

            if text is None:
                self._document_text = self._read_document_text(textfile_path)

        if text is not None:
            self._document_text = text

        Annotations.__init__(self, document=document, read_only=read_only, lock_dir=lock_dir, source=source)

    def _parse_textbound_annotation(
            self, id, data, data_tail, input_file_path):
        type, spans = self._split_textbound_data(id, data, input_file_path)

        # Verify spans
        seen_spans = []
        for start, end in spans:
            if start > end:
                self.messages.error('Text-bound annotation start > end.')
                raise IdedAnnotationLineSyntaxError(
                    id, self.ann_line, self.ann_line_num + 1, input_file_path)
            if start < 0:
                self.messages.error('Text-bound annotation start < 0.')
                raise IdedAnnotationLineSyntaxError(
                    id, self.ann_line, self.ann_line_num + 1, input_file_path)
            if end > len(self._document_text):
                self.messages.error(
                    'Text-bound annotation offset exceeds text length.')
                raise IdedAnnotationLineSyntaxError(
                    id, self.ann_line, self.ann_line_num + 1, input_file_path)

            for ostart, oend in seen_spans:
                if end >= ostart and start < oend:
                    self.messages.error('Text-bound annotation spans overlap')
                    raise IdedAnnotationLineSyntaxError(
                        id, self.ann_line, self.ann_line_num + 1, input_file_path)

            seen_spans.append((start, end))

        # first part is text, second connecting separators
        spanlen = sum([end - start for start, end in spans]) + \
            (len(spans) - 1) * len(DISCONT_SEP)

        # Require tail to be either empty or to begin with the text
        # corresponding to the catenation of the start:end spans.
        # If the tail is empty, force a fill with the corresponding text.
        if data_tail.strip() == '' and spanlen > 0:
            self.messages.error(
                u"Text-bound annotation missing text (expected format 'ID\\tTYPE START END\\tTEXT'). Filling from reference text. NOTE: This changes annotations on disk unless read-only.")
            text = "".join([self._document_text[start:end]
                            for start, end in spans])

        elif data_tail[0] != '\t':
            self.messages.error(
                'Text-bound annotation missing tab before text (expected format "ID\\tTYPE START END\\tTEXT").')
            raise IdedAnnotationLineSyntaxError(
                id, self.ann_line, self.ann_line_num + 1, input_file_path)

        elif spanlen > len(data_tail) - 1:  # -1 for tab
            self.messages.error(
                'Text-bound annotation text "%s" shorter than marked span(s) %s' % (data_tail[1:], str(spans)))
            raise IdedAnnotationLineSyntaxError(
                id, self.ann_line, self.ann_line_num + 1, input_file_path)

        else:
            text = data_tail[1:spanlen + 1]  # shift 1 for tab
            data_tail = data_tail[spanlen + 1:]

            spantexts = [self._document_text[start:end]
                         for start, end in spans]
            reftext = DISCONT_SEP.join(spantexts)

            if text != reftext:
                # just in case someone has been running an old version of
                # discont that catenated spans without DISCONT_SEP
                oldstylereftext = ''.join(spantexts)
                if text[:len(oldstylereftext)] == oldstylereftext:
                    self.messages.warning(
                        u'NOTE: replacing old-style (pre-1.3) discontinuous annotation text span with new-style one, i.e. adding space to "%s" in .ann' % text[:len(oldstylereftext)], -1)
                    text = reftext
                    data_tail = ''
                else:
                    # unanticipated mismatch
                    self.messages.error(
                        (u'Text-bound annotation text "%s" does not '
                         u'match marked span(s) %s text "%s" in document') %
                        (text, str(spans), reftext.replace(
                            '\n', '\\n')))
                    raise IdedAnnotationLineSyntaxError(
                        id, self.ann_line, self.ann_line_num + 1, input_file_path)

            if data_tail != '' and not data_tail[0].isspace():
                self.messages.error(
                    u'Text-bound annotation text "%s" not separated from rest of line ("%s") by space!' %
                    (text, data_tail))
                raise IdedAnnotationLineSyntaxError(
                    id, self.ann_line, self.ann_line_num + 1, input_file_path)

        return TextBoundAnnotationWithText(
            spans, id, type, text, data_tail, source_id=input_file_path)

    def get_document_text(self):
        return self._document_text

    def _read_document_text(self, document):
        # TODO: this is too naive; document may be e.g. "PMID.a1",
        # in which case the reasonable text file name guess is
        # "PMID.txt", not "PMID.a1.txt"
        textfn = document + '.' + TEXT_FILE_SUFFIX
        try:
            with open_textfile(textfn, 'r') as f:
                return f.read()
        except IOError:
            self.messages.error('Error reading document text from %s' % textfn)
        raise AnnotationTextFileNotFoundError(document)


class Annotation(object):
    """Base class for all annotations."""

    def __init__(self, tail, source_id=None):
        self.tail = tail
        self.source_id = source_id

    def __str__(self):
        raise NotImplementedError

    def __repr__(self):
        return u'%s("%s")' % (str(self.__class__), str(self))

    def get_deps(self):
        return (set(), set())


class UnknownAnnotation(Annotation):
    """Represents a line of annotation that could not be parsed.

    These are not discarded, but rather passed through unmodified.
    """

    def __init__(self, line, source_id=None):
        Annotation.__init__(self, line, source_id=source_id)

    def __str__(self):
        return self.tail


class UnparsedIdedAnnotation(Annotation):
    """Represents an annotation for which an ID could be read but the rest of
    the line could not be parsed.

    This is separate from UnknownAnnotation to allow IDs for unparsed
    annotations to be "reserved".
    """
    # duck-type instead of inheriting from IdedAnnotation as
    # that inherits from TypedAnnotation and we have no type

    def __init__(self, id, line, source_id=None):
        # (this actually is the whole line, not just the id tail,
        # although Annotation will assign it to self.tail)
        Annotation.__init__(self, line, source_id=source_id)
        self.id = id

    def __str__(self):
        return str(self.tail)


class TypedAnnotation(Annotation):
    """Base class for all annotations with a type."""

    def __init__(self, type, tail, source_id=None):
        Annotation.__init__(self, tail, source_id=source_id)
        self.type = type

    def __str__(self):
        raise NotImplementedError


class IdedAnnotation(TypedAnnotation):
    """Base class for all annotations with an ID."""

    def __init__(self, id, type, tail, source_id=None):
        TypedAnnotation.__init__(self, type, tail, source_id=source_id)
        self.id = id

    def reference_id(self):
        """Returns a list that uniquely identifies this annotation within its
        document."""
        return [self.id]

    def reference_text(self):
        """Returns a human-readable string that identifies this annotation
        within its document."""
        return str(self.reference_id()[0])

    def __str__(self):
        raise NotImplementedError


def split_role(r):
    """Given a string R that may be suffixed with a number, returns a tuple
    (ROLE, NUM) where ROLE+NUM == R and NUM is the maximal suffix of R
    consisting only of digits."""
    i = len(r)
    while i > 1 and r[i - 1].isdigit():
        i -= 1
    return r[:i], r[i:]


class EventAnnotation(IdedAnnotation):
    """Represents an event annotation. Events are typed annotations that are
    associated with a specific text expression stating the event (TRIGGER,
    identifying a TextBoundAnnotation) and have an arbitrary number of
    arguments, each of which is represented as a ROLE:PARTID pair, where ROLE
    is a string identifying the role (e.g. "Theme", "Cause") and PARTID the ID
    of another annotation participating in the event.

    Represented in standoff as

    ID\tTYPE:TRIGGER [ROLE1:PART1 ROLE2:PART2 ...]
    """

    def __init__(self, trigger, args, id, type, tail, source_id=None):
        IdedAnnotation.__init__(self, id, type, tail, source_id=source_id)
        self.trigger = trigger
        self.args = args

    def add_argument(self, role, argid):
        # split into "main" role label and possible numeric suffix
        role, rnum = split_role(role)
        if rnum != '':
            # if given a role with an explicit numeric suffix,
            # use the role as given (assume number is part of
            # role label).
            pass
        else:
            # find next free numeric suffix.

            # for each argument role in existing roles, determine the
            # role numbers already used
            rnums = {}
            for r, aid in self.args:
                rb, rn = split_role(r)
                if rb not in rnums:
                    rnums[rb] = {}
                rnums[rb][rn] = True

            # find the first available free number for the current role,
            # using the convention that the empty number suffix stands for 1
            rnum = ''
            while role in rnums and rnum in rnums[role]:
                if rnum == '':
                    rnum = '2'
                else:
                    rnum = str(int(rnum) + 1)

        # role+rnum is available, add
        self.args.append((role + rnum, argid))

    def __str__(self):
        return u'%s\t%s:%s %s%s' % (
            self.id,
            self.type,
            self.trigger,
            ' '.join([':'.join(map(str, arg_tup))
                      for arg_tup in self.args]),
            self.tail
        )

    def get_deps(self):
        soft_deps, hard_deps = IdedAnnotation.get_deps(self)
        hard_deps.add(self.trigger)
        arg_ids = [arg_tup[1] for arg_tup in self.args]
        # TODO: verify this logic, it's not entirely clear it's right
        if len(arg_ids) > 1:
            for arg in arg_ids:
                soft_deps.add(arg)
        else:
            for arg in arg_ids:
                hard_deps.add(arg)
        return (soft_deps, hard_deps)


class EquivAnnotation(TypedAnnotation):
    """Represents an equivalence group annotation. Equivs define a set of other
    annotations (normally TextBoundAnnotation) to be equivalent.

    Represented in standoff as

    *\tTYPE ID1 ID2 [...]

    Where "*" is the literal asterisk character.
    """

    def __init__(self, type, entities, tail, source_id=None):
        TypedAnnotation.__init__(self, type, tail, source_id=source_id)
        self.entities = entities

    def __in__(self, other):
        return other in self.entities

    def __str__(self):
        return u'*\t%s %s%s' % (
            self.type,
            ' '.join([str(e) for e in self.entities]),
            self.tail
        )

    def get_deps(self):
        soft_deps, hard_deps = TypedAnnotation.get_deps(self)
        if len(self.entities) > 2:
            for ent in self.entities:
                soft_deps.add(ent)
        else:
            for ent in self.entities:
                hard_deps.add(ent)
        return (soft_deps, hard_deps)

    def reference_id(self):
        if self.entities:
            return ['equiv', self.type, self.entities[0]]
        else:
            return ['equiv', self.type, self.entities]

    def reference_text(self):
        return '(' + ','.join([str(e) for e in self.entities]) + ')'


class AttributeAnnotation(IdedAnnotation):
    def __init__(self, target, id, type, tail, value, source_id=None):
        IdedAnnotation.__init__(self, id, type, tail, source_id=source_id)
        self.target = target
        self.value = value

    def __str__(self):
        return u'%s\t%s %s%s%s' % (
            self.id,
            self.type,
            self.target,
            # We hack in old modifiers with this trick using bools
            ' ' + str(self.value) if self.value != True else '',
            self.tail,
        )

    def get_deps(self):
        soft_deps, hard_deps = IdedAnnotation.get_deps(self)
        hard_deps.add(self.target)
        return (soft_deps, hard_deps)

    def reference_id(self):
        # TODO: can't currently ID modifier in isolation; return
        # reference to modified instead
        return [self.target]


class NormalizationAnnotation(IdedAnnotation):
    def __init__(self, id, type, target, refdb, refid, tail, source_id=None):
        IdedAnnotation.__init__(self, id, type, tail, source_id=source_id)
        self.target = target
        self.refdb = refdb
        self.refid = refid
        # "human-readable" text of referenced ID (optional)
        self.reftext = tail.lstrip('\t').rstrip('\n')

    def __str__(self):
        return u'%s\t%s %s %s:%s\t%s' % (
            self.id,
            self.type,
            self.target,
            self.refdb,
            self.refid,
            self.tail,
        )

    def get_deps(self):
        soft_deps, hard_deps = IdedAnnotation.get_deps(self)
        hard_deps.add(self.target)
        return (soft_deps, hard_deps)

    def reference_id(self):
        # TODO: can't currently ID normalization in isolation; return
        # reference to target instead
        return [self.target]


class OnelineCommentAnnotation(IdedAnnotation):
    def __init__(self, target, id, type, tail, source_id=None):
        IdedAnnotation.__init__(self, id, type, tail, source_id=source_id)
        self.target = target

    def __str__(self):
        return u'%s\t%s %s%s' % (
            self.id,
            self.type,
            self.target,
            self.tail
        )

    def get_text(self):
        # TODO: will this always hold? Wouldn't it be better to parse
        # further rather than just assuming the whole tail is the text?
        return self.tail.strip()

    def get_deps(self):
        soft_deps, hard_deps = IdedAnnotation.get_deps(self)
        hard_deps.add(self.target)
        return (soft_deps, hard_deps)


class TextBoundAnnotation(IdedAnnotation):
    """Represents a text-bound annotation. Text-bound annotations identify a
    specific span of text and assign it a type.  This base class does not
    assume ability to access text; use TextBoundAnnotationWithText for that.

    Represented in standoff as

    ID\tTYPE START END

    Where START and END are positive integer offsets identifying the
    span of the annotation in text. Discontinuous annotations can be
    represented as

    ID\tTYPE START1 END1;START2 END2;...

    with multiple START END pairs separated by semicolons.
    """

    def __init__(self, spans, id, type, tail, source_id=None):
        # Note: if present, the text goes into tail
        IdedAnnotation.__init__(self, id, type, tail, source_id=source_id)
        self.spans = spans

    # TODO: temp hack while building support for discontinuous
    # annotations; remove once done
    def get_start(self):
        self.messages.warning('TextBoundAnnotation.start access')
        return self.spans[0][0]

    def get_end(self):
        self.messages.warning('TextBoundAnnotation.end access')
        return self.spans[-1][1]
    start = property(get_start)
    end = property(get_end)
    # end hack

    def first_start(self):
        """Return the first (min) start offset in the annotation spans."""
        return min([start for start, end in self.spans])

    def last_end(self):
        """Return the last (max) end offset in the annotation spans."""
        return max([end for start, end in self.spans])

    def get_text(self):
        # If you're seeing this exception, you probably need a
        # TextBoundAnnotationWithText. The underlying issue may be
        # that you're creating an Annotations object instead of
        # TextAnnotations.
        raise NotImplementedError

    def same_span(self, other):
        """Determine if a given other TextBoundAnnotation has the same span as
        this one.

        Returns True if each (start, end) span of the other annotation
        is equivalent with at least one span of this annotation, False
        otherwise.
        """
        return set(self.spans) == set(other.spans)

    def contains(self, other):
        """Determine if a given other TextBoundAnnotation is contained in this
        one.

        Returns True if each (start, end) span of the other annotation
        is inside (or equivalent with) at least one span of this
        annotation, False otherwise.
        """
        for o_start, o_end in other.spans:
            contained = False
            for s_start, s_end in self.spans:
                if o_start >= s_start and o_end <= s_end:
                    contained = True
                    break
            if not contained:
                return False
        return True

    def __str__(self):
        return u'%s\t%s %s%s' % (
            self.id,
            self.type,
            ';'.join(['%d %d' % (start, end) for start, end in self.spans]),
            self.tail
        )


class TextBoundAnnotationWithText(TextBoundAnnotation):
    """Represents a text-bound annotation. Text-bound annotations identify a
    specific span of text and assign it a type.  This class assume that the
    referenced text is included in the annotation.

    Represented in standoff as

    ID\tTYPE START END\tTEXT

    Where START and END are positive integer offsets identifying the
    span of the annotation in text and TEXT is the corresponding text.
    Discontinuous annotations can be represented as

    ID\tTYPE START1 END1;START2 END2;...

    with multiple START END pairs separated by semicolons.
    """

    def __init__(self, spans, id, type, text, text_tail="", source_id=None):
        # For convenience, you can pass in a `TextAnnotations` object for `text`
        if isinstance(text, TextAnnotations):
            text_annotations = text
            doc_text = text.get_document_text()
            text = DISCONT_SEP.join(doc_text[start:end]
                                    for start, end in spans)
        else:
            text_annotations = None

        IdedAnnotation.__init__(
            self,
            id,
            type,
            '\t' +
            text +
            text_tail,
            source_id=source_id)
        self.spans = spans
        self.text = text
        self.text_tail = text_tail

        if text_annotations is not None:
            text_annotations.add_annotation(self)

    # TODO: temp hack while building support for discontinuous
    # annotations; remove once done
    def get_start(self):
        self.messages.warning('TextBoundAnnotationWithText.start access')
        return self.spans[0][0]

    def get_end(self):
        self.messages.warning('TextBoundAnnotationWithText.end access')
        return self.spans[-1][1]
    start = property(get_start)
    end = property(get_end)
    # end hack

    def get_text(self):
        return self.text

    def __str__(self):
        #log_info('TextBoundAnnotationWithText: __str__: "%s"' % self.text)
        return u'%s\t%s %s\t%s%s' % (
            self.id,
            self.type,
            ';'.join(['%d %d' % (start, end) for start, end in self.spans]),
            self.text,
            self.text_tail
        )


class BinaryRelationAnnotation(IdedAnnotation):
    """Represents a typed binary relation annotation. Relations are assumed not
    to be symmetric (i.e are "directed"); for equivalence relations,
    EquivAnnotation is likely to be more appropriate. Unlike events, relations
    are not associated with text expressions (triggers) stating them.

    Represented in standoff as

    ID\tTYPE ARG1:ID1 ARG2:ID2

    Where ARG1 and ARG2 are arbitrary (but not identical) labels.
    """

    def __init__(
            self,
            id,
            type,
            arg1l,
            arg1,
            arg2l,
            arg2,
            tail,
            source_id=None):
        IdedAnnotation.__init__(self, id, type, tail, source_id=source_id)
        self.arg1l = arg1l
        self.arg1 = arg1
        self.arg2l = arg2l
        self.arg2 = arg2

    def __str__(self):
        return u'%s\t%s %s:%s %s:%s%s' % (
            self.id,
            self.type,
            self.arg1l,
            self.arg1,
            self.arg2l,
            self.arg2,
            self.tail
        )

    def get_deps(self):
        soft_deps, hard_deps = IdedAnnotation.get_deps(self)
        hard_deps.add(self.arg1)
        hard_deps.add(self.arg2)
        return soft_deps, hard_deps


def _writable(sugg_path):
    if exists(sugg_path):
        # check the file itself for writability
        check_path = sugg_path
        correct_type = isfile
    else:
        # check the directory if file can be created
        check_path = dirname(sugg_path)
        correct_type = isdir
    return correct_type(check_path) and access(check_path, W_OK)


if __name__ == '__main__':
    from sys import stderr, argv
    for ann_path_i, ann_path in enumerate(argv[1:]):
        print(("%s.) '%s' " % (ann_path_i, ann_path, )
                          ).ljust(80, '#'))
        with Annotations(ann_path) as anns:
            for ann in anns:
                print(str(ann).rstrip('\n'))
