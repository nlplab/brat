#!/home/users/pontus/local/bin/python

'''
brat
TODO: DOC!

Brat Rapid Annotation Tool (brat)

Author:     Sampo   Pyysalo     <smp is s u tokyo ac jp>
Author:     Pontus  Stenetorp   <pontus is s u tokyo ac jp>
Author:     Goran   Topic       <goran is s u tokyo ac jp>
Version:    2010-01-24
'''

#TODO: Move imports into their respective functions to boost load time
from Cookie import SimpleCookie
from cgi import FieldStorage
from itertools import chain
from os import environ
from os import listdir, makedirs, system
from os.path import isdir, isfile
from os.path import join as join_path
from re import split, sub, match
import fileinput
import hashlib

# Relative library imports
import sys
import os.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'lib/simplejson-2.1.3'))
from simplejson import dumps, loads
from simplejson import dumps
#TODO: Clean up the path and imports
#

from annotation import Annotations, TEXT_FILE_SUFFIX
from annspec import physical_entity_types, event_argument_types
from verify_annotations import verify_annotation
# We should not import this in the end...
from annotation import (TextBoundAnnotation, AnnotationId, EquivAnnotation,
        EventAnnotation, ModifierAnnotation, DependingAnnotationDeleteError)

### Constants?
EDIT_ACTIONS = ['span', 'arc', 'unspan', 'unarc', 'logout']
COOKIE_ID = 'brat-cred'
DEBUG = True

# Try to import our configurations
from copy import deepcopy
from os.path import dirname
from sys import path

CONF_FNAME = 'config.py'
CONF_TEMPLATE_FNAME = 'config_template.py'
CONF_NAME = CONF_FNAME.replace('.py', '')
# Add new configuration variables here
CONF_VARIABLES = ['BASE_DIR', 'DATA_DIR', 'USERNAME', 'PASSWORD']

# We unset the path so that we can import being sure what we import
_old_path = deepcopy(path)
# Can you empty in in O(1) instead of O(N)?
while path:
    path.pop()
path.append(dirname(__file__))

try:
    # Check if the config file exists
    exec 'import {}'.format(CONF_NAME)
    # Clean up the namespace
    exec 'del {}'.format(CONF_NAME)
except ImportError:
    from sys import stderr
    print >> stderr, ('ERROR: could not find {script_dir}/{conf_fname} if '
            'this is a new install run '
            "'cp {conf_template_fname} {conf_fname}' "
            'and configure {conf_fname} to suit your environment'
            ).format(
                    script_dir=dirname(__file__),
                    conf_fname=CONF_FNAME,
                    conf_template_fname=CONF_TEMPLATE_FNAME
                    )
    exit(-1)

# Now import the actual configurations
exec 'from {} import {}'.format(CONF_NAME, ', '.join(CONF_VARIABLES))
# Restore the path
path.extend(_old_path)
# Clean the namespace
del deepcopy, dirname, path, _old_path

def is_physical_entity_type(t):
    return t in physical_entity_types

def is_event_type(t):
    # TODO: this assumption may not always hold, check properly
    return not is_physical_entity_type(t)

def possible_arc_types_from_to(from_ann, to_ann):
    if is_physical_entity_type(from_ann):
        # only possible "outgoing" edge from a physical entity is Equiv
        # to another entity of the same type.
        if from_ann == to_ann:
            return ['Equiv']
        else:
            return []
    elif is_event_type(from_ann):
        # look up the big table
        args = event_argument_types.get(from_ann, event_argument_types['default'])

        possible = []
        for a in args:
            if (to_ann in args[a] or
                is_event_type(to_ann) and 'event' in args[a]):
                possible.append(a)

        # prioritize the "possible" list so that frequent ones go first.
        # TODO: learn this from the data.
        argument_priority = { "Theme": 10, "Site" : 10 }
        possible.sort(lambda a,b : cmp(argument_priority.get(b,0), argument_priority.get(a,0)))

        return possible
    else:
        return None

def my_listdir(directory):
    return [l for l in listdir(directory)
            # XXX: A hack to remove what we don't want to be seen
            if not (l.startswith('hidden_') or l.startswith('.'))]

def directory_options(directory):
    print 'Content-Type: text/html\n'
    print "<option value=''>-- Select Document --</option>"
    dirlist = [file[0:-4] for file in my_listdir(directory)
            if file.endswith('txt')]
    dirlist.sort()
    for file in dirlist:
        print '<option>%s</option>' % file

def directories():
    print 'Content-Type: application/json\n'
    dirlist = [dir for dir in my_listdir(DATA_DIR)]
    dirlist.sort()
    response = { 'directories': dirlist }
    print dumps(response, sort_keys=True, indent=2)

#TODO: All this enrichment isn't a good idea, at some point we need an object
def enrich_json_with_text(j_dic, txt_file):
    # TODO: replace this crude heuristic with proper sentence splitting
    j_dic['text'] = sub(r'(\. *) ([A-Z])',r'\1\n\2', txt_file.read())

def enrich_json_with_data(j_dic, ann_obj):
    # We collect trigger ids to be able to link the textbound later on
    trigger_ids = set()
    for event_ann in ann_obj.get_events():
        trigger_ids.add(event_ann.trigger)
        j_dic['events'].append(
                [str(event_ann.id), event_ann.trigger, event_ann.args]
                )

    for tb_ann in ann_obj.get_textbounds():
        j_tb = [str(tb_ann.id), tb_ann.type, tb_ann.start, tb_ann.end]

        # If we spotted it in the previous pass as a trigger for an
        # event or if the type is known to be an event type, we add it
        # as a json trigger.
        if tb_ann.id in trigger_ids or is_event_type(tb_ann.type):
            j_dic['triggers'].append(j_tb)
        else: 
            j_dic['entities'].append(j_tb)

    for eq_id, eq_ann in enumerate(ann_obj.get_equivs(), start=1):
        j_dic['equivs'].append(
                (['*{}'.format(eq_id), eq_ann.type]
                    + [e for e in eq_ann.entities])
                )

    for mod_ann in ann_obj.get_modifers():
        j_dic['modifications'].append(
                [str(mod_ann.id), mod_ann.type, mod_ann.target]
                )

    for com_ann in ann_obj.get_oneline_comments():
        j_dic['infos'].append(
                [com_ann.target, com_ann.type, com_ann.tail.strip()]
                )

    if ann_obj.failed_lines:
        j_dic['error'] = 'Unable to parse the following line(s):<br/>{}'.format(
                '\n<br/>\n'.join(
                    ['{}: {}'.format(
                        str(line_num - 1),
                        str(ann_obj[line_num])
                        ).strip()
                    for line_num in ann_obj.failed_lines])
                    )
        j_dic['duration'] = len(ann_obj.failed_lines) * 3
    else:
        j_dic['error'] = None

    try:
        issues = verify_annotation(ann_obj)
    except Exception, e:
        # TODO add an issue about the failure
        issues = []
        j_dic['error']    = 'Error: verify_annotation() failed: %s' % e
        j_dic['duration'] = -1

    for i in issues:
        j_dic['infos'].append((str(i.ann_id), i.type, i.description))

def enrich_json_with_base(j_dic):
    # TODO: Make the names here and the ones in the Annotations object conform
    # This is the from offset
    j_dic['offset'] = 0
    j_dic['entities'] = []
    j_dic['events'] = []
    j_dic['triggers'] = []
    j_dic['modifications'] = []
    j_dic['equivs'] = []
    j_dic['infos'] = []

def document_json_dict(document):
    #TODO: DOC!

    j_dic = {}
    enrich_json_with_base(j_dic)

    #TODO: We don't check if the files exist, let's be more error friendly
    # Read in the textual data to make it ready to push
    with open(document + '.' + TEXT_FILE_SUFFIX, 'r') as txt_file:
        enrich_json_with_text(j_dic, txt_file)

    with Annotations(document) as ann_obj:
        enrich_json_with_data(j_dic, ann_obj)

    return j_dic

def document_json(document):
    j_dic = document_json_dict(document)
    print 'Content-Type: application/json\n'
    print dumps(j_dic, sort_keys=True, indent=2)

def saveSVG(directory, document, svg):
    dir = '/'.join([BASE_DIR, 'svg', directory])
    if not isdir(dir):
        makedirs(dir)
    basename = dir + '/' + document
    file = open(basename + '.svg', 'wb')
    file.write('<?xml version="1.0" standalone="no"?><!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">')
    defs = svg.find('</defs>')
    if defs != -1:
        css = open(BASE_DIR + '/annotator.css').read()
        css = '<style type="text/css"><![CDATA[' + css + ']]></style>'
        svg = svg[:defs] + css + svg[defs:]
        file.write(svg)
        file.close()
        # system('rsvg %s.svg %s.png' % (basename, basename))
        # print 'Content-Type: application/json\n'
        print 'Content-Type: text/plain\n'
        print 'Saved as %s in %s' % (basename + '.svg', dir)
    else:
        print 'Content-Type: text/plain'
        print 'Status: 400 Bad Request\n'


def span_types_html():
    from simplejson import dumps

    response = { }

    # reminder: if there's an error when generating (eventually), this
    # is how to get it across
#     if there_is_an_error:
#         response['error'] = 'Error message'

    # just hard-coded for now
    keymap =  {
        'P': 'Protein',
        'E': 'Entity',
        'H': 'Hydroxylation',
        'R': 'Dehydroxylation',
        'O': 'Phosphorylation',
        'U': 'Ubiquitination',
        'B': 'Deubiquitination',
        'G': 'Glycosylation',
        'L': 'Deglycosylation',
        'A': 'Acetylation',
        'T': 'Deacetylation',
        'M': 'Methylation',
        'Y': 'Demethylation',
        'D': 'DNA_methylation',
        'C': 'Catalysis',
        'N': 'mod_Negation',
        'S': 'mod_Speculation',
        }

    client_keymap = {}
    for k in keymap:
        # TODO: the info on how to format these for the client
        # should go into htmlgen
        client_keymap[k] = 'span_'+keymap[k]

    type_to_key_map = {}
    for k in keymap:
        type_to_key_map[keymap[k]] = k
    
    response['keymap'] = client_keymap

    from htmlgen import generate_span_type_html
    response['html']  = """<fieldset>
<legend>Entities</legend>
<div class="item">
  <div class="item_content">
   <input id="span_Protein" name="span_type" type="radio" value="Protein"/><label for="span_Protein"><span class="accesskey">P</span>rotein</label>
  </div>
</div>
<div class="item">
  <div class="item_content">
   <input id="span_Entity" name="span_type" type="radio" value="Entity"/><label for="span_Entity"><span class="accesskey">E</span>ntity</label>
  </div>
</div>
</fieldset>
<fieldset>
<legend>Events</legend>
<fieldset>
<legend>Type</legend>
<div id="span_scroller">
""" + generate_span_type_html(type_to_key_map) + """</div>
</fieldset>
<fieldset id="span_mod_fset">
  <legend>Modifications</legend>
  <input id="span_mod_Negation" type="checkbox" value="Negation"/>
  <label for="span_mod_Negation"><span class="accesskey">N</span>egation</label>
  <input id="span_mod_Speculation" type="checkbox" value="Speculation"/>
  <label for="span_mod_Speculation"><span class="accesskey">S</span>peculation</label>
</fieldset>
</fieldset>
"""
    
    print 'Content-Type: application/json\n'
    print dumps(response, sort_keys=True, indent=2)


def arc_types_html(origin_type, target_type):
    from simplejson import dumps

    response = { }

    try:
        possible = possible_arc_types_from_to(origin_type, target_type)

        # TODO: proper error handling
        if possible is None:
            response['error'] = 'Error selecting arc types!'
        elif possible == []:
            # nothing to select
            response['html'] = "<fieldset><legend>Type</legend>(No valid arc types)</fieldset>"
            response['keymap'] = {}
            response['empty'] = True
        else:
            # pick hotkeys
            key_taken = {}
            key_for   = {}
            response['keymap']  = { }
            for p in possible:
                for i in range(len(p)):
                    if p[i].lower() not in key_taken:
                        key_taken[p[i].lower()] = True
                        key_for[p] = p[i].lower()
                        response['keymap'][p[i].upper()] = "arc_"+p
                        break

            # generate input for each possible choice
            inputs = []
            for p in possible:
                inputstr = '<input id="arc_%s" type="radio" name="arc_type" value="%s"/>' % (p,p)
                if p not in key_for:
                    inputstr += '<label for="arc_%s">%s</label>' % (p, p)
                else:
                    accesskey = key_for[p]
                    key_offset= p.lower().find(accesskey)
                    inputstr += '<label for="arc_%s">%s<span class="accesskey">%s</span>%s</label>' % (p, p[:key_offset], p[key_offset:key_offset+1], p[key_offset+1:])
                inputs.append(inputstr)
            response['html']  = '<fieldset><legend>Type</legend>' + '\n'.join(inputs) + '</fieldset>'
    except:
        response['error'] = 'Error selecting arc types!'
    
    print 'Content-Type: application/json\n'
    print dumps(response, sort_keys=True, indent=2)


#TODO: Couldn't we incorporate this nicely into the Annotations class?
class LineModificationTracker(object):
    def __init__(self):
        self.added = []
        self.changed = []
        self.deleted = []

    def __len__(self):
        return len(self.added) + len(self.changed) + len(self.deleted)

    def change(self, before, after):
        self.changed.append(
                '\t{}\n<br/>\n\tInto:\n<br/>\t{}'.format(before, after))

    def json_response(self, response=None):
        if response is None:
            response = {}

        msg_str = ''
        if self.added:
            msg_str += ('Added the following line(s):\n<br/>'
                    + '\n<br/>\n'.join([str(a) for a in self.added]))
        if self.changed:
            msg_str += ('Changed the following line(s):\n<br/>'
                    + '\n<br/>\n'.join([str(a) for a in self.changed]))
        if self.deleted:
            msg_str += ('Deleted the following line(s):\n<br/>'
                    + '\n<br/>\n'.join([str(a) for a in self.deleted]))
        if msg_str:
            response['message'] = msg_str
            response['duration'] = 3 * len(self)
        else:
            response['message'] = 'No changes made'
        return response


#TODO: ONLY determine what action to take! Delegate to Annotations!
def save_span(document, start_str, end_str, type, negation, speculation, id):
    #TODO: Handle the case when negation and speculation both are positive
    # if id present: edit
    # if spanfrom and spanto present, new
    #XXX: Negation, speculation not done!
    txt_file_path = document + '.' + TEXT_FILE_SUFFIX

    with Annotations(document) as ann_obj:
        mods = LineModificationTracker()

        if id is not None:
            #TODO: Handle failure to find!
            ann = ann_obj.get_ann_by_id(id)
            
            # Hack to support event annotations
            try:
                if int(start_str) != ann.start or int(end_str) != ann.end:
                    # This scenario has been discussed and changing the span inevitably
                    # leads to the text span being out of sync since we can't for sure
                    # determine where in the data format the text (if at all) it is
                    # stored. For now we will fail loudly here.
                    print 'Content-Type: application/json\n'
                    error = 'unable to change the span of an existing annotation'
                    print dumps({ 'error': error }, sort_keys=True, indent=2)
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
                if ((is_event_type(ann.type)
                    and is_physical_entity_type(type))
                    or
                    (is_physical_entity_type(ann.type)
                        and is_event_type(type))):
                        # XXX: We don't allow this! Warn!
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
                                mods.added.append(new_ann_trig)
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
                                    mods.deleted.append(ann_trig)
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
                spec_mod = ModifierAnnotation(ann.id, spec_mod_id, 'Speculation', '') #XXX: Cons
                ann_obj.add_annotation(spec_mod)
                mods.added.append(spec_mod)
            if negation and seen_neg is None:
                neg_mod_id = ann_obj.get_new_id('M') #XXX: Cons
                neg_mod = ModifierAnnotation(ann.id, neg_mod_id, 'Negation', '') #XXX: Cons
                ann_obj.add_annotation(neg_mod)
                mods.added.append(neg_mod)
            # Is the attribute unset and one existing? Erase.
            if not speculation and seen_spec is not None:
                try:
                    ann_obj.del_annotation(seen_spec)
                    mods.deleted.append(seen_spec)
                except DependingAnnotationDeleteError:
                    assert False, 'Dependant attached to speculation'
            if not negation and seen_neg is not None:
                try:
                    ann_obj.del_annotation(seen_neg)
                    mods.deleted.append(seen_neg)
                except DependingAnnotationDeleteError:
                    assert False, 'Dependant attached to negation'

            # It could be the case that the span is involved in event(s), if so, 
            # the type of that event is changed
            #TODO:
        else:
            start = int(start_str)
            end = int(end_str)

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
                ann = TextBoundAnnotation(start, end, new_id, type, '\t' + text)
                ann_obj.add_annotation(ann)
                mods.added.append(ann)
            else:
                ann = found

            if is_physical_entity_type(type):
                # TODO: alert that negation / speculation are ignored if set
                pass
            else:
                # Create the event also
                new_event_id = ann_obj.get_new_id('E') #XXX: Cons
                event = EventAnnotation(ann.id, [], new_event_id, type, '')
                ann_obj.add_annotation(event)
                mods.added.append(event)

                # TODO: use an existing identical textbound for the trigger
                # if one exists, don't dup            

                if speculation:
                    spec_mod_id = ann_obj.get_new_id('M') #XXX: Cons
                    spec_mod = ModifierAnnotation(new_event_id, spec_mod_id, 'Speculation', '') #XXX: Cons
                    ann_obj.add_annotation(spec_mod)
                    mods.added.append(spec_mod)
                else:
                    neg_mod = None
                if negation:
                    neg_mod_id = ann_obj.get_new_id('M') #XXX: Cons
                    neg_mod = ModifierAnnotation(new_event_id, neg_mod_id, 'Negation', '') #XXX: Cons
                    ann_obj.add_annotation(neg_mod)
                    mods.added.append(neg_mod)
                else:
                    neg_mod = None

        print 'Content-Type: application/json\n'
        mods_json = mods.json_response()
        # save a roundtrip and send the annotations also
        j_dic = document_json_dict(document)
        mods_json["annotations"] = j_dic
        print dumps(mods_json, sort_keys=True, indent=2)
    

# XXX: This didn't really look as pretty as planned
# TODO: Prettify the decorator to preserve signature
def _annotations_decorator(doc_index_in_args, id_indexes=None):
    '''
    Decorate a function to convert the document path for a given path to an
    Annotations object upon calling. Also allows the look-up of ids turning
    them into actual annotations.

    TODO: Extensive doc
    TODO: Also raises annotation not found.
    '''
    def dec(func):
        def _func(*args):
            from copy import copy
            document = args[doc_index_in_args]
            with Annotations(document) as ann_obj:
                # We only need a shallow copy
                new_args = list(copy(args))
                new_args[doc_index_in_args] = ann_obj
                if id_indexes is not None:
                    for i in id_indexes:
                        new_args[i] = ann_obj.get_ann_by_id(args[i])
                return func(*new_args)
        return _func
    return dec
           
#TODO: Should determine which step to call next
@_annotations_decorator(0, [1, 2])
def save_arc(ann_obj, origin, target, type, old_type):
    mods = LineModificationTracker()

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
            mods.added.append(ann)
    else:
        # It is an Equiv
        assert old_type is None, 'attempting to change Equiv, not supported'
        ann = EquivAnnotation(type, [str(origin.id), str(target.id)], '')
        ann_obj.add_annotation(ann)
        mods.added.append(ann)

    print 'Content-Type: application/json\n'
    mods_json = mods.json_response()

    # Hack since we don't have the actual text, should use a factory?
    j_dic = {}
    enrich_json_with_base(j_dic)
    with open(ann_obj.get_document() + '.' + TEXT_FILE_SUFFIX, 'r') as txt_file:
        enrich_json_with_text(j_dic, txt_file)
    enrich_json_with_data(j_dic, ann_obj)
    mods_json['annotations'] = j_dic
    print dumps(mods_json, sort_keys=True, indent=2)
    
#TODO: ONLY determine what action to take! Delegate to Annotations!
def delete_span(document, id):
    id = AnnotationId(id)
    txt_file_path = document + '.' + TEXT_FILE_SUFFIX

    with Annotations(document) as ann_obj:
        mods = LineModificationTracker()
        
        #TODO: Handle a failure to find it
        #XXX: Slow, O(2N)
        ann = ann_obj.get_ann_by_id(id)
        try:
            # Note: need to pass the tracker to del_annotation to track
            # recursive deletes. TODO: make usage consistent.
            ann_obj.del_annotation(ann, mods)
            try:
                #TODO: Why do we need this conversion? Isn't it an id?
                trig = ann_obj.get_ann_by_id(AnnotationId(ann.trigger))
                try:
                    ann_obj.del_annotation(trig, mods)
                except DependingAnnotationDeleteError:
                    # Someone else depended on that trigger
                    pass
            except AttributeError:
                pass
        except DependingAnnotationDeleteError, e:
            print 'Content-Type: application/json\n'
            print dumps(e.json_error_response(), sort_keys=True, indent=2)
            return

        print 'Content-Type: application/json\n'
        mods_json = mods.json_response()
        # save a roundtrip and send the annotations also
        j_dic = document_json_dict(document)
        mods_json["annotations"] = j_dic
        print dumps(mods_json, sort_keys=True, indent=2)

#TODO: ONLY determine what action to take! Delegate to Annotations!
def delete_arc(document, origin, target, type):
    origin = AnnotationId(origin)
    target = AnnotationId(target)
    txt_file_path = document + '.' + TEXT_FILE_SUFFIX

    with Annotations(document) as ann_obj:
        mods = LineModificationTracker()

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
                        mods.deleted.append(event_ann)
                    except DependingAnnotationDeleteError, e:
                        print 'Content-Type: application/json\n'
                        print dumps(e.json_error_response(), sort_keys=True, indent=2)
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
                        mods.deleted.append(eq_ann)
                    except DependingAnnotationDeleteError, e:
                        print 'Content-Type: application/json\n'
                        print dumps(e.json_error_response(), sort_keys=True, indent=2)
                        return

        print 'Content-Type: application/json\n'
        mods_json = mods.json_response()
        # save a roundtrip and send the annotations also
        j_dic = document_json_dict(document)
        mods_json["annotations"] = j_dic
        print dumps(mods_json, sort_keys=True, indent=2)

class InvalidAuthException(Exception):
    pass

def authenticate(login, password):
    # TODO: Database back-end
    crunchyhash = hashlib.sha512(PASSWORD).hexdigest()
    if (login != USERNAME or password != crunchyhash):
        raise InvalidAuthException()

def main():
    params = FieldStorage()
    
    cookie = SimpleCookie()
    if environ.has_key('HTTP_COOKIE'):
        cookie.load(environ['HTTP_COOKIE'])
    try:
        creds = loads(cookie[COOKIE_ID].value)
    except KeyError:
        creds = {}

    directory = params.getvalue('directory')
    document = params.getvalue('document')

    if directory is None:
        input = ''
    elif document is None:
        input = directory
    else:
        input = directory + document
    if input.find('/') != -1:
        print 'Content-Type: text/plain'
        print 'Status: 403 Forbidden (slash)\n'
        return

    action = params.getvalue('action')

    if action in EDIT_ACTIONS:
        try:
            authenticate(creds['user'], creds['password'])
        except (InvalidAuthException, KeyError):
            print 'Content-Type: text/plain'
            print 'Status: 403 Forbidden (auth)\n'
            return

    if directory is None:
        if action == 'login':
            creds = {
                    'user': params.getvalue('user'),
                    'password': hashlib.sha512(
                        params.getvalue('pass')).hexdigest(),
                    }
            try:
                authenticate(creds['user'], creds['password'])
                cookie[COOKIE_ID] = dumps(creds)
                # cookie[COOKIE_ID]['max-age'] = 15*60 # 15 minutes
                print 'Content-Type: text/plain'
                print cookie
                print '\n'
                print 'Hello, %s' % creds['user']
            except InvalidAuthException:
                print 'Content-Type: text/plain'
                print 'Status: 403 Forbidden (auth)\n'

        elif action == 'logout':
            from datetime import datetime
            cookie[COOKIE_ID]['expires'] = (
                    datetime.fromtimestamp(0L).strftime(
                        '%a, %d %b %Y %H:%M:%S UTC'))
            print 'Content-Type: text/plain'
            print cookie
            print '\n'
            print 'Goodbye, %s' % creds['user']

        elif action == 'getuser':
            result = {}
            try:
                result['user'] = creds['user']
            except (KeyError):
                result['error'] = 'Not logged in'
            print 'Content-Type: application/json\n'
            print dumps(result)

        elif action == 'spantypes':
            span_types_html()

        elif action == 'arctypes':
            arc_types_html(
                params.getvalue('origin'),
                params.getvalue('target')
                )
        else:
            directories()
    else:
        real_directory = join_path(DATA_DIR, directory)

        if document is None:
            directory_options(real_directory)
        else:
            docpath = join_path(real_directory, document)
            span = params.getvalue('span')

            #XXX: Calls to save and delete can raise AnnotationNotFoundError
            # TODO: We could potentially push everything out of ajax.cgi and
            # catch anything showing up in the code and push it back to the dev.
            # For now these are the only parts that speak json
            try:
                if action == 'span':
                    save_span(docpath,
                            params.getvalue('from'),
                            params.getvalue('to'),
                            params.getvalue('type'),
                            params.getvalue('negation') == 'true',
                            params.getvalue('speculation') == 'true',
                            params.getvalue('id'))
                elif action == 'arc':
                    save_arc(docpath,
                            params.getvalue('origin'),
                            params.getvalue('target'),
                            params.getvalue('type'),
                            params.getvalue('old') or None)
                elif action == 'unspan':
                    delete_span(docpath,
                            params.getvalue('id'))
                elif action == 'unarc':
                    delete_arc(docpath,
                            params.getvalue('origin'),
                            params.getvalue('target'),
                            params.getvalue('type'))
                elif action == 'save':
                    svg = params.getvalue('svg')
                    saveSVG(directory, document, svg)
                else:
                    document_json(docpath)
            except Exception, e:
                # Catch even an interpreter crash
                if DEBUG:
                    from traceback import print_exc
                    try:
                        from cStringIO import StringIO
                    except ImportError:
                        from StringIO import StringIO

                    buf = StringIO()
                    print_exc(file=buf)
                    buf.seek(0)
                    print 'Content-Type: application/json\n'
                    error_msg = '<br/>'.join((
                    'Python crashed, we got:\n',
                    buf.read())).replace('\n', '\n<br/>\n')
                    print dumps(
                            {
                                'error': error_msg,
                                'duration': -1,
                                },
                            sort_keys=True, indent=2)
                # Allow the exception to fall through so it is logged
                raise

def debug():
    '''
    # A little bit of debug to make it easier for me // Pontus
    import os
    from difflib import unified_diff, ndiff
    from sys import stderr
    for root, dirs, files in os.walk(DATA_DIR):
        for file_path in (join_path(root, f) for f in files):
            if file_path.endswith('.ann') and not 'hidden_' in file_path:
                #if file_path.endswith('PMC2714965-02-Results-01.ann'):
                print file_path
                with open(file_path, 'r') as ann_file:
                    ann_str = ann_file.read()
                
                ann_obj_str = str(Annotations(file_path))
                print ann_obj_str

                if ann_str != ann_obj_str:
                    print >> stderr, 'MISMATCH:'
                    print >> stderr, file_path
                    print >> stderr, 'OLD:'
                    print >> stderr, ann_str
                    print >> stderr, 'NEW:'
                    print >> stderr, ann_obj_str
                    #for diff_line in unified_diff(ann_str.split('\n'),
                    #        ann_obj_str.split('\n')):
                    #    print >> stderr, diff_line,
                    exit(-1)
                
                #exit(0)
    '''

    #a = Annotations(
    #        'data/BioNLP-ST_2011_Epi_and_PTM_training_data/PMID-10190553.ann')
    #print a

    args = (('/data/home/genia/public_html/BioNLP-ST/pontus/visual/data/'
        'BioNLP-ST_2011_Epi_and_PTM_training_data/PMID-10190553'),
        '59',
        '74',
        'Protein',
        False,
        False,
        None
        )
    save_span(*args)

    '''
    args = (('/data/home/genia/public_html/BioNLP-ST/pontus/visual/data/'
        'BioNLP-ST_2011_Epi_and_PTM_training_data/PMID-10190553'),
        'T31',
        )
    delete_span(*args)
    '''

    args = (('/data/home/genia/public_html/BioNLP-ST/pontus/visual/data/'
        'BioNLP-ST_2011_Epi_and_PTM_training_data/PMID-10190553'),
        'T5',
        'T4',
        'Equiv',
        )
    save_arc(*args)
    
    args = (('/data/home/genia/public_html/BioNLP-ST/pontus/visual/data/'
        'BioNLP-ST_2011_Epi_and_PTM_development_data/PMID-10086714'),
        'E2',
        'T10',
        'Theme',
        )
    save_arc(*args)
    delete_arc(*args)


if __name__ == '__main__':
    from sys import argv
    try:
        if argv[1] == '-d':
            exit(debug())
    except IndexError:
        pass
    main() 
