#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Annotator functionality, editing and retrieving status.

Author:     Pontus Stenetorp
Version:    2011-04-22
'''

# XXX: This module is messy, re-factor to be done

from __future__ import with_statement

from os.path import join as path_join
from os.path import split as path_split

from annotation import (OnelineCommentAnnotation, TEXT_FILE_SUFFIX,
        TextAnnotations, DependingAnnotationDeleteError, TextBoundAnnotation,
        EventAnnotation, ModifierAnnotation, EquivAnnotation, open_textfile)
from config import DEBUG
from document import real_directory
from jsonwrap import loads as json_loads
from message import display_message
from projectconfig import ProjectConfiguration
from htmlgen import generate_empty_fieldset, select_keyboard_shortcuts, generate_arc_type_html

def possible_arc_types(directory, origin_type, target_type):
    real_dir = real_directory(directory)
    projectconf = ProjectConfiguration(real_dir)
    response = {}

    try:
        possible = projectconf.arc_types_from_to(origin_type, target_type)

        # TODO: proper error handling
        if possible is None:
            display_message("Error selecting arc types!", "error", -1)
        elif possible == []:
            # nothing to select
            response['html'] = generate_empty_fieldset()
            response['keymap'] = {}
            response['empty'] = True
        else:
            # pick hotkeys
            arc_kb_shortcuts = select_keyboard_shortcuts(possible)
 
            response['keymap'] = {}
            for k, p in arc_kb_shortcuts.items():
                response['keymap'][k] = "arc_"+p

            response['html']  = generate_arc_type_html(projectconf, possible, arc_kb_shortcuts)
    except:
        display_message("Error selecting arc types!", "error", -1)
        raise
    
    return response

#TODO: Couldn't we incorporate this nicely into the Annotations class?
#TODO: Yes, it is even gimped compared to what it should do when not. This
#       has been a long pending goal for refactoring.
class ModificationTracker(object):
    def __init__(self):
        self.__added = []
        self.__changed = []
        self.__deleted = []

    def __len__(self):
        return len(self.__added) + len(self.__changed) + len(self.__deleted)

    def addition(self, added):
        self.__added.append(added)

    def deletion(self, deleted):
        self.__deleted.append(deleted)

    def change(self, before, after):
        self.__changed.append((before, after))

    def json_response(self, response=None):
        if response is None:
            response = {}

        # debugging
        msg_str = ''
        if self.__added:
            msg_str += ('Added the following line(s):\n<br/>'
                    + '\n<br/>\n'.join([unicode(a) for a in self.__added]))
        if self.__changed:
            changed_strs = []
            for before, after in self.__changed:
                changed_strs.append('\t%s\n<br/>\n\tInto:\n<br/>\t%s' % (before, after))
            msg_str += ('Changed the following line(s):\n<br/>'
                    + '\n<br/>\n'.join([unicode(a) for a in changed_strs]))
        if self.__deleted:
            msg_str += ('Deleted the following line(s):\n<br/>'
                    + '\n<br/>\n'.join([unicode(a) for a in self.__deleted]))
        if msg_str:
            display_message(msg_str, duration=3*len(self))
        else:
            display_message('No changes made')

        # highlighting
        response['edited'] = []
        # TODO: implement cleanly, e.g. add a highlightid() method to Annotation classes
        for a in self.__added:
            try:
                response['edited'].append(a.reference_id())
            except AttributeError:
                pass # not all implement reference_id()
        for b,a in self.__changed:
            # can't mark "before" since it's stopped existing
            try:
                response['edited'].append(a.reference_id())
            except AttributeError:
                pass # not all implement reference_id()

        return response

def confirm_span(docdir, docname, span_id):
    document = path_join(docdir, docname)

    txt_file_path = document + '.' + TEXT_FILE_SUFFIX

    with TextAnnotations(document) as ann_obj:
        mods = ModificationTracker()

        # find AnnotationUnconfirmed comments that refer
        # to the span and remove them
        # TODO: error checking
        for ann in ann_obj.get_oneline_comments():
            if ann.type == "AnnotationUnconfirmed" and ann.target == span_id:
                ann_obj.del_annotation(ann, mods)

        print 'Content-Type: application/json\n'
        if DEBUG:
            mods_json = mods.json_response()
        else:
            mods_json = {}
        # save a roundtrip and send the annotations also
        txt_file_path = document + '.' + TEXT_FILE_SUFFIX
        j_dic = _json_from_ann_and_txt(ann_obj, txt_file_path)
        mods_json["annotations"] = j_dic
        add_messages_to_json(mods_json)
        print dumps(mods_json)

# Hack for the round-trip
def _json_from_ann_and_txt(ann_obj, txt_file_path):
    j_dic = {}
    from document import (_enrich_json_with_data, _enrich_json_with_base,
            _enrich_json_with_text)
    _enrich_json_with_base(j_dic)
    _enrich_json_with_text(j_dic, txt_file_path)
    _enrich_json_with_data(j_dic, ann_obj)
    return j_dic

### Attributes
# XXX: Temporary solution until we make a config
# XXX: We only support these two for now, don't adjust
ATTRIBUTES = set((
    'negation',
    'speculation',
    ))
ATTRIBUTE_VALUES = {
        'negation': set((
            'true',
            None,
            )),
        'speculation': set((
            'true',
            None,
            )),
        }
for attr in ATTRIBUTES:
    assert attr in ATTRIBUTE_VALUES
###

# NOTE: For now this converts into the old version for compability
def create_span(directory, document, start, end, type,
        attributes=None, id=None, comment=None):
    if attributes is None:
        # NOTE: Defaults are to be added here
        attributes = {}
    else:
        attributes =  json_loads(attributes)
        #display_message("purst" + str(attributes), "info", 10)

    for attr in attributes:
        # TODO: This is to be removed upon completed implementation
        assert attr in set(('negation', 'speculation', )), (
                'protocol not supporting general attribute "%s"' % attr)

    try:
        negation = attributes['negation']
    except KeyError:
        negation = False

    try:
        speculation = attributes['speculation']
    except KeyError:
        speculation = False

    return _create_span(directory, document, start, end,
            type, negation, speculation, id=id, comment=comment)

from logging import info as log_info
from annotation import TextBoundAnnotation, TextBoundAnnotationWithText

def _edit_span(ann_obj, mods, id, start, end, projectconf, speculation,
        negation, type):
    #TODO: Handle failure to find!
    ann = ann_obj.get_ann_by_id(id)

    if isinstance(ann, EventAnnotation):
        # We should actually modify the trigger
        tb_ann = ann_obj.get_ann_by_id(ann.trigger)
        e_ann = ann
    else:
        tb_ann = ann
        e_ann = None

    if (int(start) != tb_ann.start
            or int(end) != tb_ann.end):
        if not isinstance(tb_ann, TextBoundAnnotation):
            # This scenario has been discussed and changing the span inevitably
            # leads to the text span being out of sync since we can't for sure
            # determine where in the data format the text (if at all) it is
            # stored. For now we will fail loudly here.
            error_msg = ('unable to change the span of an existing annotation'
                    '(annotation: %s)' % repr(tb_ann))
            display_message(error_msg, type='error', duration=3)
            # Not sure if we only get an internal server error or the data
            # will actually reach the client to be displayed.
            assert False, error_msg
        else:
            # TODO: Log modification too?
            before = unicode(tb_ann)
            #log_info('Will alter span of: "%s"' % str(to_edit_span).rstrip('\n'))
            tb_ann.start = int(start)
            tb_ann.end = int(end)
            tb_ann.text = ann_obj._document_text[tb_ann.start:tb_ann.end]
            #log_info('Span altered')
            mods.change(before, tb_ann)

    if ann.type != type:
        if projectconf.type_category(ann.type) != projectconf.type_category(type):
            # TODO: Raise some sort of protocol error
            display_message("Cannot convert %s (%s) into %s (%s)"
                    % (ann.type, projectconf.type_category(ann.type),
                        type, projectconf.type_category(type)),
                    "error", -1)
            pass
        else:
            before = unicode(ann)
            ann.type = type

            # Try to propagate the type change
            try:
                #XXX: We don't take into consideration other anns with the
                # same trigger here!
                ann_trig = ann_obj.get_ann_by_id(ann.trigger)
                if ann_trig.type != ann.type:
                    # At this stage we need to determine if someone else
                    # is using the same trigger
                    if any((event_ann
                        for event_ann in ann_obj.get_events()
                        if (event_ann.trigger == ann.trigger
                                and event_ann != ann))):
                        # Someone else is using it, create a new one
                        from copy import copy
                        # A shallow copy should be enough
                        new_ann_trig = copy(ann_trig)
                        # It needs a new id
                        new_ann_trig.id = ann_obj.get_new_id('T')
                        # And we will change the type
                        new_ann_trig.type = ann.type
                        # Update the old annotation to use this trigger
                        ann.trigger = unicode(new_ann_trig.id)
                        ann_obj.add_annotation(new_ann_trig)
                        mods.addition(new_ann_trig)
                    else:
                        # Okay, we own the current trigger, but does an
                        # identical to our sought one already exist?
                        found = None
                        for tb_ann in ann_obj.get_textbounds():
                            if (tb_ann.start == ann_trig.start
                                    and tb_ann.end == ann_trig.end
                                    and tb_ann.type == ann.type):
                                found = tb_ann
                                break

                        if found is None:
                            # Just change the trigger type since we are the
                            # only users

                            before = unicode(ann_trig)
                            ann_trig.type = ann.type
                            mods.change(before, ann_trig)
                        else:
                            # Attach the new trigger THEN delete
                            # or the dep will hit you
                            ann.trigger = unicode(found.id)
                            ann_obj.del_annotation(ann_trig)
                            mods.deletion(ann_trig)
            except AttributeError:
                # It was most likely a TextBound entity
                pass

            # Finally remember the change
            mods.change(before, ann)
    # Here we assume that there is at most one of each in the file, this can be wrong
    seen_spec = None
    seen_neg = None
    for other_ann in ann_obj:
        try:
            if other_ann.target == unicode(ann.id):
                if other_ann.type == 'Speculation': #XXX: Cons
                    seen_spec = other_ann
                if other_ann.type == 'Negation': #XXX: Cons
                    seen_neg = other_ann
        except AttributeError:
            pass
    # Is the attribute set and none existing? Add.
    if speculation and seen_spec is None:
        spec_mod_id = ann_obj.get_new_id('M') #XXX: Cons
        spec_mod = ModifierAnnotation(unicode(ann.id), unicode(spec_mod_id),
                'Speculation', '') #XXX: Cons
        ann_obj.add_annotation(spec_mod)
        mods.addition(spec_mod)
    if negation and seen_neg is None:
        neg_mod_id = ann_obj.get_new_id('M') #XXX: Cons
        neg_mod = ModifierAnnotation(unicode(ann.id), unicode(neg_mod_id),
                'Negation', '') #XXX: Cons
        ann_obj.add_annotation(neg_mod)
        mods.addition(neg_mod)
    # Is the attribute unset and one existing? Erase.
    if not speculation and seen_spec is not None:
        try:
            ann_obj.del_annotation(seen_spec)
            mods.deletion(seen_spec)
        except DependingAnnotationDeleteError:
            assert False, 'Dependant attached to speculation'
    if not negation and seen_neg is not None:
        try:
            ann_obj.del_annotation(seen_neg)
            mods.deletion(seen_neg)
        except DependingAnnotationDeleteError:
            assert False, 'Dependant attached to negation'

    return tb_ann, e_ann

def __create_span(ann_obj, mods, type, start, end, txt_file_path,
        projectconf, speculation, negation):
    # TODO: Rip this out!
    start = int(start)
    end = int(end)

    # Before we add a new trigger, does it already exist?
    found = None
    for tb_ann in ann_obj.get_textbounds():
        try:
            if (tb_ann.start == start and tb_ann.end == end
                    and tb_ann.type == type):
                found = tb_ann
                break
        except AttributeError:
            # Not a trigger then
            pass

    if found is None:
        # Get a new ID
        new_id = ann_obj.get_new_id('T') #XXX: Cons
        # Get the text span
        with open_textfile(txt_file_path, 'r') as txt_file:
            text = txt_file.read()[start:end]

        #TODO: Data tail should be optional
        if '\n' not in text:
            ann = TextBoundAnnotationWithText(start, end, new_id, type, text)
            ann_obj.add_annotation(ann)
            mods.addition(ann)
        else:
            ann = None
    else:
        ann = found

    if ann is not None:
        if projectconf.is_physical_entity_type(type):
            # TODO: alert that negation / speculation are ignored if set
            event = None
        else:
            # Create the event also
            new_event_id = ann_obj.get_new_id('E') #XXX: Cons
            event = EventAnnotation(ann.id, [], unicode(new_event_id), type, '')
            ann_obj.add_annotation(event)
            mods.addition(event)

            # TODO: use an existing identical textbound for the trigger
            # if one exists, don't dup            

            if speculation:
                spec_mod_id = ann_obj.get_new_id('M') #XXX: Cons
                spec_mod = ModifierAnnotation(unicode(new_event_id),
                        unicode(spec_mod_id), 'Speculation', '') #XXX: Cons
                ann_obj.add_annotation(spec_mod)
                mods.addition(spec_mod)
            else:
                neg_mod = None
            if negation:
                neg_mod_id = ann_obj.get_new_id('M') #XXX: Cons
                neg_mod = ModifierAnnotation(unicode(new_event_id),
                        unicode(neg_mod_id), 'Negation', '') #XXX: Cons
                ann_obj.add_annotation(neg_mod)
                mods.addition(neg_mod)
            else:
                neg_mod = None
    else:
        # We got a newline in the span, don't take any action
        event = None

    return ann, event

#TODO: ONLY determine what action to take! Delegate to Annotations!
def _create_span(directory, document, start, end, type, negation, speculation,
        id=None, comment=None):
#def save_span(docdir, docname, start_str, end_str, type, negation, speculation, id):
    #TODO: Handle the case when negation and speculation both are positive
    # if id present: edit
    # if spanfrom and spanto present, new
    #XXX: Negation, speculation not done!

    # Convert from types sent by JS
    if isinstance(negation, str):
        negation = negation == 'true' 
    if isinstance(speculation, str):
        speculation = speculation == 'true'

    real_dir = real_directory(directory)
    document = path_join(real_dir, document)

    projectconf = ProjectConfiguration(real_dir)

    txt_file_path = document + '.' + TEXT_FILE_SUFFIX

    working_directory = path_split(document)[0]

    with TextAnnotations(document) as ann_obj:
        mods = ModificationTracker()

        if id is not None:
            # We are to edit an existing annotation
            tb_ann, e_ann = _edit_span(ann_obj, mods, id, start, end, projectconf,
                    speculation, negation, type)
        else:
            # We are to create a new annotation
            tb_ann, e_ann = __create_span(ann_obj, mods, type, start, end, txt_file_path,
                    projectconf, speculation, negation)

        if tb_ann is not None:
            if DEBUG:
                mods_json = mods.json_response()
            else:
                mods_json = {}
        else:
            # Hack, we had a new-line in the span
            mods_json = {}
            display_message('Text span contained new-line, rejected',
                    type='error', duration=3)

        # Handle annotation comments
        if tb_ann is not None:
            # If this is an event, we want to attach the comment to it
            if e_ann is not None:
                comment_on = e_ann
            else:
                comment_on = tb_ann

            # We are only interested in id;ed comments
            try:
                comment_on.id
                has_id = True
            except AttributeError:
                has_id = False

            if has_id:
                # Check if there is already an annotation comment
                for com_ann in ann_obj.get_oneline_comments():
                    if (com_ann.type == 'AnnotatorNotes'
                            and com_ann.target == comment_on.id):
                        found = com_ann
                        break
                else:
                    found = None

                if comment:
                    if found is not None:
                        # Change the comment
                        # XXX: Note the ugly tab, it is for parsing the tail
                        found.tail = '\t' + comment
                    else:
                        # Create a new comment
                        ann_obj.add_annotation(
                                OnelineCommentAnnotation(
                                    comment_on.id, ann_obj.get_new_id('#'),
                                    # XXX: Note the ugly tab
                                    'AnnotatorNotes', '\t' + comment)
                                )
                else:
                    # We are to erase the annotation
                    if found is not None:
                        ann_obj.del_annotation(found)

        # save a roundtrip and send the annotations also
        txt_file_path = document + '.' + TEXT_FILE_SUFFIX
        j_dic = _json_from_ann_and_txt(ann_obj, txt_file_path)
        mods_json['annotations'] = j_dic

        return mods_json
    
from annotation import BinaryRelationAnnotation

#TODO: Should determine which step to call next
#def save_arc(directory, document, origin, target, type, old_type=None):
def create_arc(directory, document, origin, target, type,
        old_type=None, old_target=None):
    real_dir = real_directory(directory)
    mods = ModificationTracker()

    real_dir = real_directory(directory)
    projectconf = ProjectConfiguration(real_dir)

    document = path_join(real_dir, document)

    with TextAnnotations(document) as ann_obj:
        origin = ann_obj.get_ann_by_id(origin) 
        target = ann_obj.get_ann_by_id(target)

        # Ugly check, but we really get no other information
        if type == 'Equiv':
            # It is an Equiv
            if old_type == "Equiv":
                # "Change" from Equiv to Equiv is harmless
                # TODO: some message needed?
                pass
            else:
                assert old_type is None, 'attempting to change Equiv, not supported'
                ann = EquivAnnotation(type, [unicode(origin.id), unicode(target.id)], '')
                ann_obj.add_annotation(ann)
                mods.addition(ann)
        elif type in projectconf.get_relation_types():
            if old_type is not None or old_target is not None:
                assert type in projectconf.get_relation_types(), (
                        ('attempting to convert relation to non-relation "%s" ' % (target.type, )) +
                        ('(legit types: %s)' % (unicode(projectconf.get_relation_types()), )))

                sought_target = (old_target
                        if old_target is not None else target.id)
                sought_type = (old_type
                        if old_type is not None else type)

                # We are to change the type and/or target
                found = None
                for ann in ann_obj.get_relations():
                    if ann.arg2 == sought_target and ann.type == sought_type:
                        found = ann
                        break

                # Did it exist and is changed?, otherwise we do nothing
                if found is not None and (found.arg2 != target.id
                        or found.type != type):
                    before = unicode(found)
                    found.arg2 = target.id
                    found.type = type
                    mods.change(before, found)
            else:
                # Create a new annotation

                # TODO: Assign a suitable letter
                new_id = ann_obj.get_new_id('R')
                ann = BinaryRelationAnnotation(new_id, type, origin.id, target.id, '\t')
                mods.addition(ann)
                ann_obj.add_annotation(ann)
        else:
            try:
                arg_tup = (type, unicode(target.id))
                
                # Is this an addition or an update?
                if old_type is None and old_target is None:
                    if arg_tup not in origin.args:
                        before = unicode(origin)
                        origin.args.append(arg_tup)
                        mods.change(before, origin)
                    else:
                        # It already existed as an arg, we were called to do nothing...
                        pass
                else:
                    # Construct how the old arg would have looked like
                    old_arg_tup = (type if old_type is None else old_type,
                            target if old_target is None else old_target)

                    if old_arg_tup in origin.args and arg_tup not in origin.args:
                        before = unicode(origin)
                        origin.args.remove(old_arg_tup)
                        origin.args.append(arg_tup)
                        mods.change(before, origin)
                    else:
                        # Collision etc. don't do anything
                        pass
            except AttributeError:
                # The annotation did not have args, it was most likely an entity
                # thus we need to create a new Event...
                new_id = ann_obj.get_new_id('E')
                ann = EventAnnotation(
                            origin.id,
                            [arg_tup],
                            new_id,
                            origin.type,
                            ''
                            )
                ann_obj.add_annotation(ann)
                mods.addition(ann)

        if DEBUG:
            mods_json = mods.json_response()
        else:
            mods_json = {}

        # Hack since we don't have the actual text, should use a factory?
        txt_file_path = ann_obj.get_document() + '.' + TEXT_FILE_SUFFIX
        j_dic = _json_from_ann_and_txt(ann_obj, txt_file_path)

        mods_json['annotations'] = j_dic
        return mods_json

#TODO: ONLY determine what action to take! Delegate to Annotations!
def delete_arc(directory, document, origin, target, type):
    real_dir = real_directory(directory)
    document = path_join(real_dir, document)

    txt_file_path = document + '.' + TEXT_FILE_SUFFIX

    with TextAnnotations(document) as ann_obj:
        mods = ModificationTracker()

        # This can be an event or an equiv
        #TODO: Check for None!
        try:
            event_ann = ann_obj.get_ann_by_id(origin)
            # Try if it is an event
            arg_tup = (type, unicode(target))
            if arg_tup in event_ann.args:
                before = unicode(event_ann)
                event_ann.args.remove(arg_tup)
                mods.change(before, event_ann)

                '''
                if not event_ann.args:
                    # It was the last argument tuple, remove it all
                    try:
                        ann_obj.del_annotation(event_ann)
                        mods.deletion(event_ann)
                    except DependingAnnotationDeleteError, e:
                        #XXX: Old message api
                        print 'Content-Type: application/json\n'
                        print dumps(e.json_error_response())
                        return
                '''
            else:
                # What we were to remove did not even exist in the first place
                pass

        except AttributeError:
            projectconf = ProjectConfiguration(real_dir)
            if type == 'Equiv':
                # It is an equiv then?
                #XXX: Slow hack! Should have a better accessor! O(eq_ann)
                for eq_ann in ann_obj.get_equivs():
                    # We don't assume that the ids only occur in one Equiv, we
                    # keep on going since the data "could" be corrupted
                    if (unicode(origin) in eq_ann.entities
                            and unicode(target) in eq_ann.entities):
                        before = unicode(eq_ann)
                        eq_ann.entities.remove(unicode(origin))
                        eq_ann.entities.remove(unicode(target))
                        mods.change(before, eq_ann)

                    if len(eq_ann.entities) < 2:
                        # We need to delete this one
                        try:
                            ann_obj.del_annotation(eq_ann)
                            mods.deletion(eq_ann)
                        except DependingAnnotationDeleteError, e:
                            #TODO: This should never happen, dep on equiv
                            #print 'Content-Type: application/json\n'
                            # TODO: Proper exception here!
                            display_message(e.json_error_response(), type='error', duration=3)
                            #print dumps(add_messages_to_json({}))
                            return {}
            elif type in projectconf.get_relation_types():
                for ann in ann_obj.get_relations():
                    if ann.type == type and ann.arg1 == origin and ann.arg2 == target:
                        ann_obj.del_annotation(ann)
                        mods.deletion(ann)
                        break
            else:
                assert False, 'unknown annotation'

        if DEBUG:
            mods_json = mods.json_response()
        else:
            mods_json = {}
        # save a roundtrip and send the annotations also
        txt_file_path = document + '.' + TEXT_FILE_SUFFIX
        j_dic = _json_from_ann_and_txt(ann_obj, txt_file_path)
        mods_json['annotations'] = j_dic
        return mods_json

#TODO: ONLY determine what action to take! Delegate to Annotations!
def delete_span(directory, document, id):
    real_dir = real_directory(directory)
    document = path_join(real_dir, document)
    
    txt_file_path = document + '.' + TEXT_FILE_SUFFIX

    with TextAnnotations(document) as ann_obj:
        mods = ModificationTracker()
        
        #TODO: Handle a failure to find it
        #XXX: Slow, O(2N)
        ann = ann_obj.get_ann_by_id(id)
        try:
            # Note: need to pass the tracker to del_annotation to track
            # recursive deletes. TODO: make usage consistent.
            ann_obj.del_annotation(ann, mods)
            try:
                trig = ann_obj.get_ann_by_id(ann.trigger)
                try:
                    ann_obj.del_annotation(trig, mods)
                except DependingAnnotationDeleteError:
                    # Someone else depended on that trigger
                    pass
            except AttributeError:
                pass
        except DependingAnnotationDeleteError, e:
            display_message(e.html_error_str(), type='error', duration=3)
            return {
                    'exception': True,
                    }

        #print 'Content-Type: application/json\n'
        if DEBUG:
            mods_json = mods.json_response()
        else:
            mods_json = {}
        # save a roundtrip and send the annotations also
        txt_file_path = document + '.' + TEXT_FILE_SUFFIX
        j_dic = _json_from_ann_and_txt(ann_obj, txt_file_path)
        mods_json["annotations"] = j_dic
        return mods_json

from common import ProtocolError

class AnnotationSplitError(ProtocolError):
    def __init__(self, message):
        self.message = message

    def json(self, json_dic):
        json_dic['exception'] = 'annotationSplitError'
        display_message(self.message, 'error')
        return json_dic

def split_span(directory, document, args, id):
    real_dir = real_directory(directory)
    document = path_join(real_dir, document)
    # TODO don't know how to pass an array directly, so doing extra catenate and split
    tosplit_args = args.split('|')
    
    txt_file_path = document + '.' + TEXT_FILE_SUFFIX

    with TextAnnotations(document) as ann_obj:
        mods = ModificationTracker()
        
        ann = ann_obj.get_ann_by_id(id)

        # currently only allowing splits for events
        if not isinstance(ann, EventAnnotation):
            raise AnnotationSplitError("Cannot split an annotation of type %s" % ann.type)

        # group event arguments into ones that will be split on and
        # ones that will not, placing the former into a dict keyed by
        # the argument without trailing numbers (e.g. "Theme1" ->
        # "Theme") and the latter in a straight list.
        split_args = {}
        nonsplit_args = []
        import re
        for arg, aid in ann.args:
            m = re.match(r'^(.*?)\d*$', arg)
            if m:
                arg = m.group(1)
            if arg in tosplit_args:
                if arg not in split_args:
                    split_args[arg] = []
                split_args[arg].append(aid)
            else:
                nonsplit_args.append((arg, aid))

        # verify that split is possible
        for a in tosplit_args:
            acount = len(split_args.get(a,[]))
            if acount < 2:
                raise AnnotationSplitError("Cannot split %s on %s: only %d %s arguments (need two or more)" % (ann.id, a, acount, a))

        # create all combinations of the args on which to split
        argument_combos = [[]]
        for a in tosplit_args:
            new_combos = []
            for aid in split_args[a]:
                for c in argument_combos:
                    new_combos.append(c + [(a, aid)])
            argument_combos = new_combos

        # create the new events (first combo will use the existing event)
        from copy import deepcopy
        new_events = []
        for i, arg_combo in enumerate(argument_combos):
            # tweak args
            if i == 0:
                ann.args = nonsplit_args[:] + arg_combo
            else:
                newann = deepcopy(ann)
                newann.id = ann_obj.get_new_id("E") # TODO: avoid hard-coding ID prefix
                newann.args = nonsplit_args[:] + arg_combo
                ann_obj.add_annotation(newann)
                new_events.append(newann)

        # then, go through all the annotations referencing the original
        # event, and create appropriate copies
        for a in ann_obj:
            soft_deps, hard_deps = a.get_deps()
            refs = soft_deps | hard_deps
            if ann.id in refs:
                # Referenced; make duplicates appropriately

                if isinstance(a, EventAnnotation):
                    # go through args and make copies for referencing
                    new_args = []
                    for arg, aid in a.args:
                        if aid == ann.id:
                            for newe in new_events:
                                new_args.append((arg, newe.id))
                    a.args.extend(new_args)

                elif isinstance(a, ModifierAnnotation):
                    for newe in new_events:
                        newmod = deepcopy(a)
                        newmod.target = newe.id
                        newmod.id = ann_obj.get_new_id("M") # TODO: avoid hard-coding ID prefix
                        ann_obj.add_annotation(newmod)

                elif isinstance(a, BinaryRelationAnnotation):
                    # TODO
                    raise AnnotationSplitError("Cannot adjust annotation referencing split: not implemented for relations! (WARNING: annotations may be in inconsistent state, please reload!) (Please complain to the developers to fix this!)")

                elif isinstance(a, OnelineCommentAnnotation):
                    # TODO
                    raise AnnotationSplitError("Cannot adjust annotation referencing split: not implemented for comments! (WARNING: annotations may be in inconsistent state, please reload!) (Please complain to the developers to fix this!)")

                else:
                    raise AnnotationSplitError("Cannot adjust annotation referencing split: not implemented for %s! (Please complain to the lazy developers to fix this!)" % a.__class__)

        #print 'Content-Type: application/json\n'
        if DEBUG:
            mods_json = mods.json_response()
        else:
            mods_json = {}
        # save a roundtrip and send the annotations also
        txt_file_path = document + '.' + TEXT_FILE_SUFFIX
        j_dic = _json_from_ann_and_txt(ann_obj, txt_file_path)
        mods_json["annotations"] = j_dic
        return mods_json

def set_status(directory, document, status=None):
    real_dir = real_directory(directory) 

    with TextAnnotations(path_join(real_dir, document)) as ann:
        # Erase all old status annotations
        for status in ann.get_statuses():
            ann.del_annotation(status)
        
        if status is not None:
            # XXX: This could work, not sure if it can induce an id collision
            new_status_id = ann.get_new_id('#')
            ann.add_annotation(OnelineCommentAnnotation(
                new_status, new_status_id, 'STATUS', ''
                ))

    json_dic = {
            'status': new_status
            }
    return json_dic

def get_status(directory, document):
    with TextAnnotations(path_join(real_directory, document),
            read_only=True) as ann:

        # XXX: Assume the last one is correct if we have more
        #       than one (which is a violation of protocol anyway)
        statuses = [c for c in ann.get_statuses()]
        if statuses:
            status = statuses[-1].target
        else:
            status = None

    json_dic = {
            'status': status
            }
    return json_dic
