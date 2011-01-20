#!/data/home/pontus/local/bin/python

#XXX: The above is a hack to get a non-ancient Python

#!/usr/bin/env python

#TODO: Move imports into their respective functions to boost load time
from cgi import FieldStorage
from os import listdir, makedirs, system
from os.path import isdir, isfile
from os.path import join as join_path
from re import split, sub, match
from itertools import chain
import fileinput

from annspec import physical_entity_types, event_argument_types
from verify_annotations import verify_annotation

### Constants?
EDIT_ACTIONS = ['span', 'arc', 'unspan', 'unarc', 'auth']
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
    def __init__(self, ann_path):
        #TODO: DOC!
        #TODO: Incorparate file locking! Is the destructor called upon inter crash?
        from collections import defaultdict

        self.ann_path = ann_path

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
        self._parse_ann_file()

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

    def del_annotation(self, ann, recursive=True):
        # Recursive controls if we are allowed to cascade or raises an excep.
        #TODO: DOC!
        #TODO:
        #XXX: We will have cascades here! This is only for atomics
        self._atomic_del_annotation(ann)

        """
        soft_deps, hard_deps = ann.get_deps()
        if (soft_deps or hard_deps) and not recursive:
            #TODO: Requires permissions some exception!
            raise NotImplementedError

        #TODO: Traverse all deps and erase once they get atomic!

        # Now it is fine to delete out annotation
        self._atomic_del_annotation(ann)
        """

    def _atomic_del_annotation(self, ann):
        #TODO: DOC
        # Erase the ann by id shorthand
        del self._ann_by_id[ann.id]
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

    def _parse_ann_file(self):
        from itertools import takewhile
        # If you knew the format, you would have used regexes...
        #
        # We use ids internally since otherwise we need to resolve a dep graph
        # when parsing to make sure we have the annotations to refer to.
        with open(self.ann_path, 'r') as ann_file:
            #XXX: Assumptions start here...
            for ann_line in ann_file:
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
        super(TypedAnnotation, self).__init__(tail)
        self.type = type

    def __str__(self):
        raise NotImplementedError


class IdedAnnotation(TypedAnnotation):
    def __init__(self, id, type, tail):
        super(IdedAnnotation, self).__init__(type, tail)
        self.id = id

    def __str__(self):
        raise NotImplementedError


class EventAnnotation(IdedAnnotation):
    #TODO: It is not called target is it?
    def __init__(self, trigger, args, id, type, tail):
        super(EventAnnotation, self).__init__(id, type, tail)
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
        soft_deps, hard_deps = super(self).get_deps()
        hard_deps.add(self.trigger)
        arg_ids = [arg_tup[1] for arg_tup in self.args]
        if len(arg_ids) > 1:
            soft_deps.union(set(arg_ids))
        else:
            hard_deps.union(set(arg_ids))
        return (soft_deps, hard_deps)


class EquivAnnotation(TypedAnnotation):
    def __init__(self, type, entities, tail):
        super(EquivAnnotation, self).__init__(type, tail)
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
        soft_deps, hard_deps = super(self).get_deps()
        if len(self.entities) > 1:
            soft_deps.union(set(self.entities))
        else:
            hard_deps.union(set(self.entities))
        return (soft_deps, hard_deps)


class ModifierAnnotation(IdedAnnotation):
    def __init__(self, target, id, type, tail):
        super(ModifierAnnotation, self).__init__(id, type, tail)
        self.target = target
        
    def __str__(self):
        return '{id}\t{type} {target}{tail}'.format(
                id=self.id,
                type=self.type,
                target=self.target,
                tail=self.tail
                )

    def get_deps(self):
        soft_deps, hard_deps = super(self).get_deps()
        hard_deps.append(self.target)
        return (soft_deps, hard_deps)


class TextBoundAnnotation(IdedAnnotation):
    def __init__(self, start, end, id, type, tail):
        #XXX: Note that the text goes in the tail! 
        super(TextBoundAnnotation, self).__init__(id, type, tail)
        self.start = start
        self.end = end
        #self.text = text

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
    from simplejson import dumps

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

    ann_obj = Annotations(ann_file_path)

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

    possible = possible_arc_types_from_to(origin_type, target_type)

    response = { 'types' : [], 'message' : None, 'category' : None }

    # TODO: proper error handling
    if possible is None:
        response['message'] = 'Error selecting arc types!'
        response['category'] = 'error'
    elif possible == []:
        response['message'] = 'No choices for %s -> %s' % (origin_type, target_type)
        response['category'] = 'error'
    else:
        response['types']   = [['Arcs', possible]]
        
    print 'Content-Type: application/json\n'
    print dumps(response, sort_keys=True, indent=2)

def save_span(document, start_str, end_str, type, negation, speculation, id):
    #TODO: Handle the case when negation and speculation both are positive
    # if id present: edit
    # if spanfrom and spanto present, new
    #XXX: Negation, speculation not done!
    ann_file_path = document + '.' + ANN_FILE_SUFFIX
    txt_file_path = document + '.' + TEXT_FILE_SUFFIX

    ann_obj = Annotations(ann_file_path)
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

    try:
        issues = verify_annotation(ann_obj)
        print 'Issues:', issues
    except Exception, e:
        print "Failed to run verify_annotation! %s" % e
        issues = []
        # TODO add an issue about the failure

    with open(ann_file_path, 'w') as ann_file:
        for i in issues:
            print >> ann_file, i
        ann_file.write(str(ann_obj))

def save_arc(document, origin, target, type):
    # (arcorigin, arctarget) is unique
    # if exists before, replace
    
    ann_file_path = document + '.' + ANN_FILE_SUFFIX
    txt_file_path = document + '.' + TEXT_FILE_SUFFIX

    ann_obj = Annotations(ann_file_path)

    #TODO: Check for None!
    orig_ann = ann_obj.get_ann_by_id(origin)
    try:
        arg_tup = (type, target)
        if (target, target) not in orig_ann.args:
            orig_ann.args.append(arg_tup)
        else:
            # It already existed, we were called to do nothing...
            pass
    except AttributeError:
        # The annotation did not have args, it was most likely an entity
        # thus we need to create a new Event...
        #TODO: You need to do merging of EquivAnnotation, in add_annotation...
        ann_obj.add_annotation(EquivAnnotation('Equiv', set([origin, target]), ''))

    print 'Content-Type: text/html\n'
    print 'Added', document, origin, target, type
    
    with open(ann_file_path, 'w') as ann_file:
        ann_file.write(str(ann_obj))

def delete_span(document, id):
    ann_file_path = document + '.' + ANN_FILE_SUFFIX
    txt_file_path = document + '.' + TEXT_FILE_SUFFIX

    ann_obj = Annotations(ann_file_path)
    
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

    ann_obj = Annotations(ann_file_path)

    print 'Content-Type: text/html\n'
    #TODO: Check for None!
    orig_ann = ann_obj.get_ann_by_id(origin)
    arg_tup = (type, target)
    print arg_tup
    print orig_ann.args
    if arg_tup in orig_ann.args:
        orig_ann.args.remove(arg_tup)
        if not orig_ann.args:
            # It was the last argument tuple, remove it all
            ann_obj.del_annotation(orig_ann)
    else:
        # What we were to remove did not even exist in the first place
        pass

    print 'Deleted', document, origin, target, type
    
    with open(ann_file_path, 'w') as ann_file:
        ann_file.write(str(ann_obj))

def authenticate(username, password):
    # TODO: Should use a backend
    return (username == USERNAME and password == PASSWORD)

def main():
    params = FieldStorage()
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
        user = params.getvalue('user')
        if not authenticate(user, params.getvalue('pass')):
            print 'Content-Type: text/plain'
            print 'Status: 403 Forbidden (auth)\n'
            return

    if directory is None:
        if action == 'auth':
            print 'Content-Type: text/plain\n'
            print 'Hello, %s' % user
        elif action == 'arctypes':
            arc_types_html(
                params.getvalue('origin'),
                params.getvalue('target'))
        else:
            directories()
    else:
        real_directory = DATA_DIR + '/' + directory

        if document is None:
            directory_options(real_directory)
        else:
            # XXX: check that the path doesn't refer up the directory tree (e.g. "../../")
            docpath = real_directory + '/' + document
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

if __name__ == '__main__':
    from sys import argv
    try:
        if argv[1] == '-d':
            exit(debug())
    except IndexError:
        pass
    main()
