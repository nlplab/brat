#!/data/home/pontus/local/bin/python
# coding=utf-8

'''
Brat (/brât/)
TODO: DOC!

Author:     Sampo   Pyysalo     <smp is s u tokyo ac jp>
Author:     Pontus  Stenetorp   <pontus is s u tokyo ac jp>
Author:     Goran   Topič       <smp is s u tokyo ac jp>
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

#TODO: __str__ for the errors
#TODO: Rename and re-work this one
class AnnotationLineSyntaxError(Exception):
    def __init__(self, line):
        self.line = line


class AnnotationNotFoundError(Exception):
    def __init__(self, id):
        self.id = id


class DuplicateAnnotationIdError(Exception):
    def __init__(self, id):
        self.id = id


class InvalidIdError(Exception):
    def __init__(self, id):
        self.id = id


def _split_id(id):
    '''
    Split an id into its prefix and numerical component.

    id format: [A-Za-z]+[0-9]+

    Arguments:
    id - a valid id

    Returns:
    A tuple containing the id prefix and number

    Raises:
    InvalidIdError - if the format of the id is invalid
    '''
    from itertools import takewhile

    id_pre = ''.join([char for char in takewhile(
        lambda c : not c.isdigit(), id)])
    if not id_pre:
        raise InvalidIdError(id)

    try:
        id_num = int(id[len(id_pre):])
    except ValueError:
        raise InvalidIdError(id)

    return (id_pre, id_num)


# We are NOT concerned with the conformity to the text file
class Annotations(object):
    #TODO: DOC!
    #TODO: We should handle ID collisions somehow upon initialisation
    def __init__(self, ann_iter):
        #TODO: DOC!
        #TODO: Incorparate file locking! Is the destructor called upon inter crash?
        from collections import defaultdict

        ### Here be dragons, these objects need constant updating and syncing
        # Annotation for each line of the file
        self._lines = []
        # Mapping between annotation objects and which line they occur on
        # Range: [0, inf.) unlike [1, inf.) which is common for files
        self._line_by_ann = {}
        # Maximum id number used for each id prefix, to speed up id generation
        self._max_id_num_by_prefix = defaultdict(lambda : 1)
        # Annotation by id, not includid non-ided annotations 
        self._ann_by_id = {}
        # 
        ###

        # Finally, parse the given annotation file
        self._parse_ann_file(ann_iter)

    def get_events(self):
        return (a for a in self if isinstance(a, EventAnnotation))

    def get_equivs(self):
        return (a for a in self if isinstance(a, EquivAnnotation))

    def get_textbounds(self):
        return (a for a in self if isinstance(a, TextBoundAnnotation))

    def get_modifers(self):
        return (a for a in self if isinstance(a, ModifierAnnotation))

    # TODO: getters for other categories of annotations

    def add_annotation(self, ann):
        #TODO: DOC!
        
        # Equivs have to be merged with other equivs
        try:
            # Bail as soon as possible for non-equivs
            ann.entities
            merge_cand = ann
            for eq_ann in self.get_equivs():
                try:
                    # Make sure that this Equiv duck quacks
                    eq_ann.entities
                except AttributeError, e:
                    assert False, 'got a non-entity from an entity call'

                # Do we have an entitiy in common with this equiv?
                for ent in merge_cand.entities:
                    if ent in eq_ann.entities:
                        for m_ent in merge_cand.entities:
                            if m_ent not in eq_ann.entities: 
                                eq_ann.entities.append(m_ent)
                        # Don't try to delete ann since it never was added
                        if merge_cand != ann:
                            self.del_annotation(merge_cand)
                        merge_cand = eq_ann
                        # We already merged it all, break to the next ann
                        break

            if merge_cand != ann:
                # The proposed annotation was simply merged, no need to add it
                return

        except AttributeError:
            #XXX: This can catch a ton more than we want to! Ugly!
            # It was not an Equiv, skip along
            pass

        # Register the object id
        try:
            id_pre, id_num = _split_id(ann.id)
            self._ann_by_id[ann.id] = ann
            self._max_id_num_by_prefix[id_pre] = max(id_num, 
                    self._max_id_num_by_prefix[id_pre])
        except AttributeError:
            # The annotation simply lacked an id which is fine
            pass

        # Add the annotation as the last line
        self._lines.append(ann)
        self._line_by_ann[ann] = len(self) - 1 

    def _ann_deps(ann):
        #TODO: DOC
        hard_deps = []
        soft_deps = []
       
        raise NotImplementedError
        """
        try:
            

            for other_ann in ann.
        except AttributeError:
            # So it wasn't an EventAnnotation then
            pass
        """
        
        return (soft_deps, hard_deps)

    def del_annotation(self, ann):
        #TODO: Flag to allow recursion
        #TODO: Sampo wants to allow delet of direct deps but not indirect, one step
        #TODO: DOC!
        try:
            ann.id
        except AttributeError:
            # If it doesn't have an id, nothing can depend on it
            self._atomic_del_annotation(ann)
            return

        for other_ann in self:
            soft_deps, hard_deps = other_ann.get_deps()
            if ann.id in soft_deps or ann.id in hard_deps:
                # Recursive controls if we are allowed to cascade or raises an excep.
                return #XXX: We can't do this! It is a cascade!
        self._atomic_del_annotation(ann)

    def _atomic_del_annotation(self, ann):
        #TODO: DOC
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
        for l_num in xrange(ann_line, len(self)):
            self._line_by_ann[self[l_num]] = l_num
    
    def get_ann_by_id(self, id):
        #TODO: DOC
        try:
            return self._ann_by_id[id]
        except KeyError:
            raise AnnotationNotFoundError(id)

    def get_new_id(self, id_pre):
        '''
        Return a new valid unique id for this annotation file for the given
        prefix. No ids are re-used for traceability over time for annotations,
        but this only holds for the lifetime of the annotation object. If the
        annotation file is parsed once again into an annotation object the
        next assigned id will be the maximum seen for a given prefix plus one
        which could have been deleted during a previous annotation session.

        Warning: get_new_id('T') == get_new_id('T')
        Just calling this method does not reserve the id, you need to
        add the annotation with the returned id to the annotation object in
        order to reserve it.

        Argument(s):
        id_pre - an annotation prefix on the format [A-Za-z]+

        Returns:
        An id that is guaranteed to be unique for the lifetime of the
        annotation.
        '''
        return id_pre + str(self._max_id_num_by_prefix[id_pre] + 1)

    def _parse_ann_file(self, ann_iter):
        from itertools import takewhile
        # If you knew the format, you would have used regexes...
        #
        # We use ids internally since otherwise we need to resolve a dep graph
        # when parsing to make sure we have the annotations to refer to.

        #XXX: Assumptions start here...
        for ann_line in ann_iter:
        #for ann_line in (l.rstrip('\n') for l in ann_file):
            try:
                # ID processing
                id, id_tail = ann_line.split('\t', 1)
                if id in self._ann_by_id:
                    raise DuplicateAnnotationIdError(id)
                try:
                    id_pre, id_num = _split_id(id)
                except InvalidIdError:
                    # This is silly, we call it an id_pre although for
                    # example * is not an id_pre since it is not an id at
                    # all?
                    id_pre = id
                    id_num = None

                # Cases for lines
                try:
                    data_delim = id_tail.index('\t')
                    data, data_tail = (id_tail[:data_delim],
                            id_tail[data_delim:])
                except ValueError:
                    data = id_tail
                    # No tail at all, although it should have a \t
                    data_tail = ''

                if id_pre == '*':
                    type, type_tail = data.split(None, 1)
                    # For now we can only handle Equivs
                    if type != 'Equiv':
                        raise AnnotationLineSyntaxError(ann_line)
                    equivs = type_tail.split(None)
                    self.add_annotation(
                            EquivAnnotation(type, equivs, data_tail))
                elif id_pre == 'E':
                    #XXX: A bit nasty, we require a single space
                    try:
                        type_delim = data.index(' ')
                        type_trigger, type_trigger_tail = (data[:type_delim],
                                data[type_delim:])
                    except ValueError:
                        type_trigger = data
                        type_trigger_tail = None

                    try:
                        type, trigger = type_trigger.split(':')
                    except ValueError:
                        #XXX: Stupid event without a trigger, bacteria task
                        raise AnnotationLineSyntaxError(ann_line)

                    #if type_trigger_tail == ' ':
                    #    args = []
                    if type_trigger_tail is not None:
                        args = [tuple(arg.split(':'))
                                for arg in type_trigger_tail.split()]
                    else:
                        args = []

                    self.add_annotation(EventAnnotation(
                        trigger, args, id, type, data_tail))
                elif id_pre == 'R':
                    raise NotImplementedError
                elif id_pre == 'M':
                    type, target = data.split()
                    self.add_annotation(ModifierAnnotation(
                        target, id, type, data_tail))
                elif id_pre == 'T' or id_pre == 'W':
                    type, start_str, end_str = data.split(None, 3)
                    # Abort if we have trailing values
                    if any((c.isspace() for c in end_str)):
                        raise AnnotationLineSyntaxError(ann_line)
                    start, end = (int(start_str), int(end_str))
                    #txt_file.seek(start)
                    #text = txt_file.read(end - start)
                    self.add_annotation(TextBoundAnnotation(
                        start, end, id, type, data_tail))
                elif id_pre == '#':
                    # XXX: properly process comments!
                    pass
                else:
                    #assert False, ann_line #XXX: REMOVE!
                    raise AnnotationLineSyntaxError(ann_line)
                    #assert False, 'No code to handle exception type'
            except AnnotationLineSyntaxError, e:
                #TODO: Print warning here, how do we print to console in a CGI?
                # We could not parse the line, just add it as an unknown annotation
                self.add_annotation(Annotation(e.line))

    def __str__(self):
        s = '\n'.join(str(ann).rstrip('\n') for ann in self)
        return s if s[-1] == '\n' else s + '\n'

    def __it__(self):
        for ann in self._lines:
            yield ann

    def __getitem__(self, val):
        try:
            # First, try to use it as a slice object
            return self._lines[val.start, val.stop, val.step]
        except AttributeError:
            # It appears not to be a slice object, try an index
            return self._lines[val]

    def __len__(self):
        return len(self._lines)

    def __in__(self, other):
        pass

#XXX: You are not using __init__ correctly!
#TODO: No annotation annotation, for blank lines etc.?, no just annotation tail
class Annotation(object):
    def __init__(self, tail):
        self.tail = tail

    def __str__(self):
        return self.tail
    
    def get_deps(self):
        return (set(), set())


class TypedAnnotation(Annotation):
    def __init__(self, type, tail):
        Annotation.__init__(self, tail)
        self.type = type

    def __str__(self):
        raise NotImplementedError


class IdedAnnotation(TypedAnnotation):
    def __init__(self, id, type, tail):
        TypedAnnotation.__init__(self, type, tail)
        self.id = id

    def __str__(self):
        raise NotImplementedError


class EventAnnotation(IdedAnnotation):
    #TODO: It is not called target is it?
    def __init__(self, trigger, args, id, type, tail):
        IdedAnnotation.__init__(self, id, type, tail)
        self.trigger = trigger
        self.args = args

    def __str__(self):
        return '{id}\t{type}:{trigger} {args}{tail}'.format(
                id=self.id,
                type=self.type,
                trigger=self.trigger,
                args=' '.join([':'.join(arg_tup) for arg_tup in self.args]),
                tail=self.tail
                )

    def get_deps(self):
        soft_deps, hard_deps = IdedAnnotation.get_deps(self)
        hard_deps.add(self.trigger)
        arg_ids = [arg_tup[1] for arg_tup in self.args]
        if len(arg_ids) > 1:
            for arg in arg_ids:
                soft_deps.add(arg)
        else:
            for arg in arg_ids:
                hard_deps.add(arg)
        return (soft_deps, hard_deps)


class EquivAnnotation(TypedAnnotation):
    def __init__(self, type, entities, tail):
        TypedAnnotation.__init__(self, type, tail)
        self.entities = entities

    def __in__(self, other):
        return other in self.entities

    def __str__(self):
        return '*\t{type} {equivs}{tail}'.format(
                type=self.type,
                equivs=' '.join(self.entities),
                tail=self.tail
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


class ModifierAnnotation(IdedAnnotation):
    def __init__(self, target, id, type, tail):
        IdedAnnotation.__init__(self, id, type, tail)
        self.target = target
        
    def __str__(self):
        return '{id}\t{type} {target}{tail}'.format(
                id=self.id,
                type=self.type,
                target=self.target,
                tail=self.tail
                )

    def get_deps(self):
        soft_deps, hard_deps = IdedAnnotation.get_deps(self)
        hard_deps.add(self.target)
        return (soft_deps, hard_deps)


# NOTE: The actual text goes into the tail
class TextBoundAnnotation(IdedAnnotation):
    def __init__(self, start, end, id, type, tail):
        IdedAnnotation.__init__(self, id, type, tail)
        self.start = start
        self.end = end

    def __str__(self):
        return '{id}\t{type} {start} {end}{tail}'.format(
                id=self.id,
                type=self.type,
                start=self.start,
                end=self.end,
                tail=self.tail
                )
###

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
    print 'Content-Type: text/html\n'
    print "<option value=''>-- Select Directory --</option>"
    dirlist = [dir for dir in my_listdir(DATA_DIR)]
    dirlist.sort()
    for dir in dirlist:
        print '<option>%s</option>' % dir

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
        text = sub(r'\. ([A-Z])',r'.\n\1', text_file.read())

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

    foundfiles = [document+ext for ext in (".a1", ".a2") #, ".co", ".rel")
                  if isfile(document+ext)]

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
                [event_ann.id, event_ann.trigger, event_ann.args]
                )

    for tb_ann in ann_obj.get_textbounds():
        j_tb = [tb_ann.id, tb_ann.type, tb_ann.start, tb_ann.end]

        # If we spotted it in the previous pass as a trigger for an event, we
        # only add it as a json trigger.
        if tb_ann.id in trigger_ids:
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
                [mod_ann.id, mod_ann.type, mod_ann.target]
                )

    j_dic['error'] = None

    try:
        issues = verify_annotation(ann_obj)
    except Exception, e:
        # TODO add an issue about the failure
        issues = []

    for i in issues:
        j_dic['infos'].append((i.ann_id, i.type, i.description))

    print dumps(j_dic, sort_keys=True, indent=2)
    
def saveSVG(directory, document, svg):
    dir = '/'.join([BASE_DIR, 'svg', directory])
    if not isdir(dir):
        makedirs(dir)
    basename = dir + '/' + document
    file = open(basename + '.svg', "wb")
    file.write('<?xml version="1.0" standalone="no"?><!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">')
    defs = svg.find('</defs>')
    if defs != -1:
        css = open(BASE_DIR + '/annotator.css').read()
        css = '<style type="text/css"><![CDATA[' + css + ']]></style>'
        svg = svg[:defs] + css + svg[defs:]
        file.write(svg)
        file.close()
        # system('rsvg %s.svg %s.png' % (basename, basename))
        # print "Content-Type: application/json\n"
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
            response["message"] = "Error selecting arc types!"
            response["category"] = "error"
        elif possible == []:
            response["message"] = "No choices for %s -> %s" % (origin_type, target_type)
            response["category"] = "error"
        else:
            response["types"]   = [["Arcs", possible]]
    except:
        response["message"] = "Error selecting arc types!"
        response["category"] = "error"
    
    print 'Content-Type: application/json\n'
    print dumps(response, sort_keys=True, indent=2)

def save_span(document, start_str, end_str, type, negation, speculation, id):
    #TODO: Handle the case when negation and speculation both are positive
    # if id present: edit
    # if spanfrom and spanto present, new
    #XXX: Negation, speculation not done!
    ann_file_path = document + '.' + ANN_FILE_SUFFIX
    txt_file_path = document + '.' + TEXT_FILE_SUFFIX

    with open(ann_file_path) as ann_file:
        ann_obj = Annotations(ann_file)
    if id is not None:
        #TODO: Handle failure to find!
        ann = ann_obj.get_ann_by_id(id)
        
        # We can't update start end as it is, read more below
        """
        if start != ann.start or end != ann.end:
            '''
            This scenario has been discussed and changing the span inevitably
            leads to the text span being out of sync since we can't for sure
            determine where in the data format the text (if at all) it is
            stored. For now we will fail loudly here.
            '''
            assert False, 'unable to change the span of an existing textual annotation'

        ann.start = start
        ann.end = end
        """
        ann.type = type

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
        if negation and seen_neg is None:
            neg_mod_id = ann_obj.get_new_id('M') #XXX: Cons
            neg_mod = ModifierAnnotation(ann.id, neg_mod_id, 'Negation', '') #XXX: Cons
            ann_obj.add_annotation(neg_mod)
        # Is the attribute unset and one existing? Erase.
        if not speculation and seen_spec is not None:
            ann_obj.del_annotation(seen_spec)
        if not negation and seen_neg is not None:
            ann_obj.del_annotation(seen_neg)

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

        if speculation:
            spec_mod_id = ann_obj.get_new_id('M') #XXX: Cons
            spec_mod = ModifierAnnotation(new_id, spec_mod_id, 'Speculation', '') #XXX: Cons
            ann_obj.add_annotation(spec_mod)
        else:
            neg_mod = None
        if negation:
            neg_mod_id = ann_obj.get_new_id('M') #XXX: Cons
            neg_mod = ModifierAnnotation(new_id, neg_mod_id, 'Negation', '') #XXX: Cons
            ann_obj.add_annotation(neg_mod)
        else:
            neg_mod = None

    print 'Content-Type: text/html\n'
    print 'save_span:', document, start_str, end_str, type, negation, speculation, id
    
    print 'Resulting line:', ann

    with open(ann_file_path, 'w') as ann_file:
        ann_file.write(str(ann_obj))

def save_arc(document, origin, target, type):
    ann_file_path = document + '.' + ANN_FILE_SUFFIX
    txt_file_path = document + '.' + TEXT_FILE_SUFFIX

    with open(ann_file_path) as ann_file:
        ann_obj = Annotations(ann_file)

    # Ugly check, but we really get no other information
    if type != 'Equiv':
        target_ann = ann_obj.get_ann_by_id(target)
        try:
            orig_ann = ann_obj.get_ann_by_id(origin)
            arg_tup = (type, target_ann.id)
            if arg_tup not in orig_ann.args:
                orig_ann.args.append(arg_tup)
            else:
                # It already existed as an arg, we were called to do nothing...
                pass
        except AttributeError:
            # The annotation did not have args, it was most likely an entity
            # thus we need to create a new Event...
            new_id = ann_obj.get_new_id('E')
            ann_obj.add_annotation(
                    EventAnnotation(
                        origin,
                        [arg_tup],
                        new_id,
                        orig_ann.type,
                        ''
                        ))
    else:
        # It is an Equiv
        ann_obj.add_annotation(EquivAnnotation(type, [origin, target], ''))

    print 'Content-Type: text/html\n'
    print 'Added', document, origin, target, type
  
    #XXX: Convert the string, THEN write or you cock up the file, blanking it
    with open(ann_file_path, 'w') as ann_file:
        ann_file.write(str(ann_obj))

def delete_span(document, id):
    ann_file_path = document + '.' + ANN_FILE_SUFFIX
    txt_file_path = document + '.' + TEXT_FILE_SUFFIX

    with open(ann_file_path) as ann_file:
        ann_obj = Annotations(ann_file)
    
    #TODO: Handle a failure to find it
    #XXX: Slow, O(2N)
    ann = ann_obj.get_ann_by_id(id)
    ann_obj.del_annotation(ann)

    #TODO: Handle consequences of removal, should be in the object

    print 'Content-Type: text/html\n'
    print 'Deleted', document, id # TODO do something with it

    with open(ann_file_path, 'w') as ann_file:
        ann_file.write(str(ann_obj))

def delete_arc(document, origin, target, type):
    ann_file_path = document + '.' + ANN_FILE_SUFFIX
    txt_file_path = document + '.' + TEXT_FILE_SUFFIX

    with open(ann_file_path) as ann_file:
        ann_obj = Annotations(ann_file)

    # This can be an event or an equiv

    print 'Content-Type: text/html\n'
    #TODO: Check for None!
    try:
        event_ann = ann_obj.get_ann_by_id(origin)
        # Try if it is an event
        arg_tup = (type, target)
        #print arg_tup
        #print orig_ann.args
        if arg_tup in event_ann.args:
            event_ann.args.remove(arg_tup)
            if not event_ann.args:
                # It was the last argument tuple, remove it all
                ann_obj.del_annotation(event_ann)
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
                    eq_ann.entities.remove(origin)
                    eq_ann.entities.remove(target)

                if len(eq_ann.entities) < 2:
                    # We need to delete this one
                    ann_obj.del_annotation(eq_ann)


    print 'Deleted', document, origin, target, type
    
    with open(ann_file_path, 'w') as ann_file:
        ann_file.write(str(ann_obj))

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
            print "Content-Type: text/plain"
            print "Status: 403 Forbidden (auth)\n"
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

    '''
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
        'T5',
        'T4',
        'Equiv',
        )
    save_arc(*args)
    #def save_arc(document, origin, target, type, equiv):

if __name__ == '__main__':
    from sys import argv
    try:
        if argv[1] == '-d':
            exit(debug())
    except IndexError:
        pass
    main()
