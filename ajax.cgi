#!/data/home/pontus/local/bin/python
# coding=utf-8

'''
Brat (/brât/)
TODO: DOC!

Author:     Sampo   Pyysalo     <smp is s u tokyo ac jp>
Author:     Pontus  Stenetorp   <pontus is s u tokyo ac jp>
Author:     Goran   Topič       <goran is s u tokyo ac jp>
Version:    2010-01-24
'''

#XXX: The above is a hack to get a non-ancient Python

#!/usr/bin/env python

#TODO: Move imports into their respective functions to boost load time
from cgi import FieldStorage
from os import listdir, makedirs, system
from os.path import isdir, isfile
from os.path import join as join_path
from Cookie import SimpleCookie
from os import environ
import hashlib
from re import split, sub, match
from simplejson import dumps, loads
from itertools import chain
import fileinput

from simplejson import dumps

from annspec import physical_entity_types, event_argument_types
from verify_annotations import verify_annotation
from annotation import Annotations
# We should not import this in the end...
from annotation import TextBoundAnnotation, AnnotationId, EquivAnnotation, EventAnnotation

### Constants?
EDIT_ACTIONS = ['span', 'arc', 'unspan', 'unarc', 'logout']
COOKIE_ID = 'brat-cred'
TEXT_FILE_SUFFIX = 'txt'
ANN_FILE_SUFFIX = 'ann'

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

def document_json(document):
    #TODO: DOC!
    #TODO: Shouldn't this print be in the end? Or even here?
    print 'Content-Type: application/json\n'
    from_offset = 0
    to_offset = None

    #TODO: We don't check if the files exist, let's be more error friendly
    txt_file_path = document + '.' + TEXT_FILE_SUFFIX
    ann_file_path = document + '.' + ANN_FILE_SUFFIX

    # Read in the textual data to make it ready to push
    with open(txt_file_path, 'rb') as text_file:
        # TODO: replace this crude heuristic with proper sentence splitting
        text = sub(r'(\. *) ([A-Z])',r'\1\n\2', text_file.read())

    # Dictionary to be converted into JSON
    # TODO: Make the names here and the ones in the Annotations object conform
    j_dic = {
            'offset':           from_offset,
            'text':             text,
            'entities':         [],
            'events':           [],
            'triggers':         [],
            'modifications':    [],
            'equivs':           [],
            'infos':            [],
            }

    # if the basic annotation file does not exist, fall back
    # to reading from a set of separate ones (e.g. ".a1" and ".a2").

    foundfiles = [document + '.'  + ext for ext in ('a1', 'a2')
            #, 'co', 'rel')
            if isfile(document+'.'+ext)]

    if isfile(ann_file_path):
        ann_iter = open(ann_file_path, 'r')
    elif foundfiles:
        ann_iter = fileinput.input(foundfiles)
    else:
        ann_iter = []

    ann_obj = Annotations(ann_iter)

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

def arc_types_html(origin_type, target_type):
    from simplejson import dumps

    response = { 'types' : [], 'message' : None, 'category' : None }

    try:
        possible = possible_arc_types_from_to(origin_type, target_type)

        # TODO: proper error handling
        if possible is None:
            response['message'] = 'Error selecting arc types!'
            response['category'] = 'error'
        elif possible == []:
            response['message'] = 'No choices for %s -> %s' % (origin_type, target_type)
            response['category'] = 'error'
        else:
            response['types']   = [['Arcs', possible]]
    except:
        response['message'] = 'Error selecting arc types!'
        response['category'] = 'error'
    
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
    ann_file_path = document + '.' + ANN_FILE_SUFFIX
    txt_file_path = document + '.' + TEXT_FILE_SUFFIX

    with open(ann_file_path) as ann_file:
        ann_obj = Annotations(ann_file)

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
            before = str(ann)
            ann.type = type
            mods.change(before, ann)

            # Try to propagate the type change
            try:
                #XXX: We don't take into consideration other anns with the
                # same trigger here!
                ann_trig = ann_obj.get_ann_by_id(ann.trigger)
                if ann_trig.type != ann.type:
                    before = str(ann_trig)
                    ann_trig.type = ann.type
                    mods.change(before, ann_trig)
            except AttributeError:
                # It was most likely a TextBound entity
                pass

        # Here we assume that there is at most one of each in the file, this can be wrong
        seen_spec = None
        seen_neg = None
        for other_ann in ann_obj:
            try:
                if other_ann.target == ann.id:
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

    with open(ann_file_path, 'w') as ann_file:
        ann_file.write(str(ann_obj))

    print 'Content-Type: application/json\n'
    print dumps(mods.json_response(), sort_keys=True, indent=2)

#TODO: ONLY determine what action to take! Delegate to Annotations!
#TODO: When addin an equiv the modification tracker won't really show what is
# correct since it can't know about merging
def save_arc(document, origin, target, type):
    origin = AnnotationId(origin)
    target = AnnotationId(target)
    ann_file_path = document + '.' + ANN_FILE_SUFFIX
    txt_file_path = document + '.' + TEXT_FILE_SUFFIX

    with open(ann_file_path) as ann_file:
        ann_obj = Annotations(ann_file)
    
    mods = LineModificationTracker()

    # Ugly check, but we really get no other information
    if type != 'Equiv':
        target_ann = ann_obj.get_ann_by_id(target)
        try:
            orig_ann = ann_obj.get_ann_by_id(origin)
            arg_tup = (type, str(target_ann.id))
            if arg_tup not in orig_ann.args:
                before = str(orig_ann)
                orig_ann.args.append(arg_tup)
                mods.change(before, orig_ann)
            else:
                # It already existed as an arg, we were called to do nothing...
                pass
        except AttributeError:
            # The annotation did not have args, it was most likely an entity
            # thus we need to create a new Event...
            new_id = ann_obj.get_new_id('E')
            ann = EventAnnotation(
                        origin,
                        [arg_tup],
                        new_id,
                        orig_ann.type,
                        ''
                        )
            ann_obj.add_annotation(ann)
            mods.added.append(ann)
    else:
        # It is an Equiv
        ann = EquivAnnotation(type, [origin, target], '')
        ann_obj.add_annotation(ann)
        mods.added.append(ann)

    #XXX: Convert the string, THEN write or you cock up the file, blanking it
    with open(ann_file_path, 'w') as ann_file:
        ann_file.write(str(ann_obj))

    print 'Content-Type: application/json\n'
    print dumps(mods.json_response(), sort_keys=True, indent=2)

#TODO: ONLY determine what action to take! Delegate to Annotations!
def delete_span(document, id):
    id = AnnotationId(id)
    ann_file_path = document + '.' + ANN_FILE_SUFFIX
    txt_file_path = document + '.' + TEXT_FILE_SUFFIX

    with open(ann_file_path) as ann_file:
        ann_obj = Annotations(ann_file)
    
    mods = LineModificationTracker()
    
    #TODO: Handle a failure to find it
    #XXX: Slow, O(2N)
    ann = ann_obj.get_ann_by_id(id)
    try:
        ann_obj.del_annotation(ann)
        mods.deleted.append(ann)
        try:
            #TODO: Why do we need this conversion? Isn't it an id?
            trig = ann_obj.get_ann_by_id(AnnotationId(ann.trigger))
            try:
                ann_obj.del_annotation(trig)
                mods.deleted.append(trig)
                
                # We can't do this at this stage, to be removed before ann
                '''
                for mod_ann in ann_obj.get_modifers():
                    if mod_ann.target == ann.id:
                        try:
                            ann_obj.del_annotation(trig)
                            mods.deleted.append(trig)
                        except DependingAnnotationDeleteError:
                            assert False, 'insane'
                '''
            except DependingAnnotationDeleteError:
                assert False, 'insane'
        except AttributeError:
            pass
    except DependingAnnotationDeleteError, e:
        print 'Content-Type: application/json\n'
        print dumps(e.json_error_response(), sort_keys=True, indent=2)
        return

    with open(ann_file_path, 'w') as ann_file:
        ann_file.write(str(ann_obj))
    
    print 'Content-Type: application/json\n'
    print dumps(mods.json_response(), sort_keys=True, indent=2)

#TODO: ONLY determine what action to take! Delegate to Annotations!
def delete_arc(document, origin, target, type):
    origin = AnnotationId(origin)
    target = AnnotationId(target)
    ann_file_path = document + '.' + ANN_FILE_SUFFIX
    txt_file_path = document + '.' + TEXT_FILE_SUFFIX

    with open(ann_file_path) as ann_file:
        ann_obj = Annotations(ann_file)

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
            if origin in eq_ann.entities and target in eq_ann.entities:
                before = str(eq_ann)
                eq_ann.entities.remove(origin)
                eq_ann.entities.remove(target)
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

    with open(ann_file_path, 'w') as ann_file:
        ann_file.write(str(ann_obj))

    print 'Content-Type: application/json\n'
    print dumps(mods.json_response(), sort_keys=True, indent=2)

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
                        params.getvalue('type'))
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
    
    args = (('/data/home/genia/public_html/BioNLP-ST/pontus/visual/data/'
        'BioNLP-ST_2011_Epi_and_PTM_training_data/PMID-10190553'),
        'T31',
        )
    delete_span(*args)

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
