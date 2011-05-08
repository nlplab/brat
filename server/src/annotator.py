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
        Annotations, DependingAnnotationDeleteError, TextBoundAnnotation,
        EventAnnotation, ModifierAnnotation, EquivAnnotation)
from config import DEBUG
from document import real_directory
from message import display_message
from projectconfig import ProjectConfiguration
from htmlgen import generate_empty_fieldset, select_keyboard_shortcuts, generate_arc_type_html

def possible_arc_types(directory, origin_type, target_type):
    real_dir = real_directory(directory)
    projectconfig = ProjectConfiguration(real_dir)
    response = {}

    try:
        possible = projectconfig.arc_types_from_to(origin_type, target_type)

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
                response['keymap'][k] = "arc_"+p.lower()

            response['html']  = generate_arc_type_html(possible, arc_kb_shortcuts)
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
                    + '\n<br/>\n'.join([str(a) for a in self.__added]))
        if self.__changed:
            changed_strs = []
            for before, after in self.__changed:
                changed_strs.append('\t%s\n<br/>\n\tInto:\n<br/>\t%s' % (before, after))
            msg_str += ('Changed the following line(s):\n<br/>'
                    + '\n<br/>\n'.join([str(a) for a in changed_strs]))
        if self.__deleted:
            msg_str += ('Deleted the following line(s):\n<br/>'
                    + '\n<br/>\n'.join([str(a) for a in self.__deleted]))
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

    with Annotations(document) as ann_obj:
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

#TODO: ONLY determine what action to take! Delegate to Annotations!
def create_span(directory, document, start, end, type, negation, speculation, id=None):
#def save_span(docdir, docname, start_str, end_str, type, negation, speculation, id):
    #TODO: Handle the case when negation and speculation both are positive
    # if id present: edit
    # if spanfrom and spanto present, new
    #XXX: Negation, speculation not done!

    # Convert from types sent by JS
    negation = negation == 'true'
    speculation = speculation == 'true'

    real_dir = real_directory(directory)
    document = path_join(real_dir, document)

    projectconfig = ProjectConfiguration(real_dir)

    txt_file_path = document + '.' + TEXT_FILE_SUFFIX

    working_directory = path_split(document)[0]

    with Annotations(document) as ann_obj:
        mods = ModificationTracker()

        if id is not None:
            #TODO: Handle failure to find!
            ann = ann_obj.get_ann_by_id(id)
            
            # Hack to support event annotations
            try:
                if int(start) != ann.start or int(end) != ann.end:
                    # This scenario has been discussed and changing the span inevitably
                    # leads to the text span being out of sync since we can't for sure
                    # determine where in the data format the text (if at all) it is
                    # stored. For now we will fail loudly here.
                    error_msg = 'unable to change the span of an existing annotation'
                    display_message(error_msg, type='error', duration=3)
                    # Not sure if we only get an internal server error or the data
                    # will actually reach the client to be displayed.
                    assert False, error
                    
                    # Span changes are as of yet unsupported
                    #ann.start = start
                    #ann.end = end
            except AttributeError:
                 # It is most likely an event annotion
                pass

            if ann.type != type:
                if projectconfig.type_category(ann.type) != projectconfig.type_category(type):
                    display_message("Cannot convert %s (%s) into %s (%s)" % (ann.type, projectconfig.type_category(ann.type), type, projectconfig.type_category(type)), "error", -1)
                    pass
                else:
                    before = str(ann)
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
                                ann.trigger = str(new_ann_trig.id)
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

                                    before = str(ann_trig)
                                    ann_trig.type = ann.type
                                    mods.change(before, ann_trig)
                                else:
                                    # Attach the new trigger THEN delete
                                    # or the dep will hit you
                                    ann.trigger = str(found.id)
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
                    if other_ann.target == str(ann.id):
                        if other_ann.type == 'Speculation': #XXX: Cons
                            seen_spec = other_ann
                        if other_ann.type == 'Negation': #XXX: Cons
                            seen_neg = other_ann
                except AttributeError:
                    pass
            # Is the attribute set and none existing? Add.
            if speculation and seen_spec is None:
                spec_mod_id = ann_obj.get_new_id('M') #XXX: Cons
                spec_mod = ModifierAnnotation(str(ann.id), str(spec_mod_id),
                        'Speculation', '') #XXX: Cons
                ann_obj.add_annotation(spec_mod)
                mods.addition(spec_mod)
            if negation and seen_neg is None:
                neg_mod_id = ann_obj.get_new_id('M') #XXX: Cons
                neg_mod = ModifierAnnotation(str(ann.id), str(neg_mod_id),
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

            # It could be the case that the span is involved in event(s), if so, 
            # the type of that event is changed
            #TODO:
        else:
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
                with open(txt_file_path, 'r') as txt_file:
                    txt_file.seek(start)
                    text = txt_file.read(end - start)
                        
                #TODO: Data tail should be optional
                if '\n' not in text:
                    ann = TextBoundAnnotation(start, end, new_id, type, '\t' + text)
                    ann_obj.add_annotation(ann)
                    mods.addition(ann)
                else:
                    ann = None
            else:
                ann = found

            if ann is not None:
                if projectconfig.is_physical_entity_type(type):
                    # TODO: alert that negation / speculation are ignored if set
                    pass
                else:
                    # Create the event also
                    new_event_id = ann_obj.get_new_id('E') #XXX: Cons
                    event = EventAnnotation(ann.id, [], str(new_event_id), type, '')
                    ann_obj.add_annotation(event)
                    mods.addition(event)

                    # TODO: use an existing identical textbound for the trigger
                    # if one exists, don't dup            

                    if speculation:
                        spec_mod_id = ann_obj.get_new_id('M') #XXX: Cons
                        spec_mod = ModifierAnnotation(str(new_event_id),
                                str(spec_mod_id), 'Speculation', '') #XXX: Cons
                        ann_obj.add_annotation(spec_mod)
                        mods.addition(spec_mod)
                    else:
                        neg_mod = None
                    if negation:
                        neg_mod_id = ann_obj.get_new_id('M') #XXX: Cons
                        neg_mod = ModifierAnnotation(str(new_event_id),
                                str(neg_mod_id), 'Negation', '') #XXX: Cons
                        ann_obj.add_annotation(neg_mod)
                        mods.addition(neg_mod)
                    else:
                        neg_mod = None
            else:
                # We got a newline in the span, don't take any action
                pass

        if ann is not None:
            if DEBUG:
                mods_json = mods.json_response()
            else:
                mods_json = {}
        else:
            # Hack, we had a new-line in the span
            mods_json = {}
            display_message('Text span contained new-line, rejected',
                    type='error', duration=3)
        # save a roundtrip and send the annotations also
        txt_file_path = document + '.' + TEXT_FILE_SUFFIX
        j_dic = _json_from_ann_and_txt(ann_obj, txt_file_path)
        mods_json['annotations'] = j_dic

        return mods_json
           
#TODO: Should determine which step to call next
#def save_arc(directory, document, origin, target, type, old_type=None):
def create_arc(directory, document, origin, target, type, old_type=None):
    real_dir = real_directory(directory)
    mods = ModificationTracker()

    document = path_join(real_dir, document)

    with Annotations(document) as ann_obj:
        origin, target = ann_obj.get_ann_by_id(origin), ann_obj.get_ann_by_id(target)

        # Ugly check, but we really get no other information
        if type != 'Equiv':
            try:
                arg_tup = (type, str(target.id))
                if old_type is None:
                    old_arg_tup = None
                else:
                    old_arg_tup = (old_type, str(target.id))

                if old_arg_tup is None:
                    if arg_tup not in origin.args:
                        before = str(origin)
                        origin.args.append(arg_tup)
                        mods.change(before, origin)
                    else:
                        # It already existed as an arg, we were called to do nothing...
                        pass
                else:
                    if old_arg_tup in origin.args and arg_tup not in origin.args:
                        before = str(origin)
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
        else:
            # It is an Equiv
            if old_type == "Equiv":
                # "Change" from Equiv to Equiv is harmless
                # TODO: some message needed?
                pass
            else:
                assert old_type is None, 'attempting to change Equiv, not supported'
                ann = EquivAnnotation(type, [str(origin.id), str(target.id)], '')
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

    with Annotations(document) as ann_obj:
        mods = ModificationTracker()

        # This can be an event or an equiv
        #TODO: Check for None!
        try:
            event_ann = ann_obj.get_ann_by_id(origin)
            # Try if it is an event
            arg_tup = (type, str(target))
            if arg_tup in event_ann.args:
                before = str(event_ann)
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
            # It is an equiv then?
            #XXX: Slow hack! Should have a better accessor! O(eq_ann)
            for eq_ann in ann_obj.get_equivs():
                # We don't assume that the ids only occur in one Equiv, we
                # keep on going since the data "could" be corrupted
                if (str(origin) in eq_ann.entities
                        and str(target) in eq_ann.entities):
                    before = str(eq_ann)
                    eq_ann.entities.remove(str(origin))
                    eq_ann.entities.remove(str(target))
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

    with Annotations(document) as ann_obj:
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

def set_status(directory, document, status=None):
    real_dir = real_directory(directory) 

    with Annotations(path_join(real_dir, document)) as ann:
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
    with Annotations(path_join(real_directory, document),
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
