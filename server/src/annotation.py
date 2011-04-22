#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

from __future__ import with_statement

'''
Functionality related to the annotation file format.

Author:     Pontus Stenetorp   <pontus is s u tokyo ac jp>
Version:    2010-01-25
'''

# TODO: Major re-work, cleaning up and conforming with new server paradigm

from os import utime
from time import time

from config import DATA_DIR
from common import ProtocolError
from message import display_message

### Constants
# The only suffix we allow to write to, which is the joined annotation file
JOINED_ANN_FILE_SUFF = 'ann'
# These file suffixes indicate partial annotations that can not be written to
# since they depend on multiple files for completeness
PARTIAL_ANN_FILE_SUFF = ['a1', 'a2', 'co', 'rel']
TEXT_FILE_SUFFIX = 'txt'
###

class AnnotationLineSyntaxError(Exception):
    def __init__(self, line, line_num):
        self.line = line
        self.line_num = line_num

    def __str__(self):
        'Syntax error on line %d: "%s"' % (line_num, line)


class AnnotationNotFoundError(Exception):
    def __init__(self, id):
        self.id = id

    def __str__(self):
        return 'Could not find an annotation with id: %s' % (self.id, )


class AnnotationsIsReadOnlyError(ProtocolError):
    def __init__(self):
        pass

    def json(self, json_dic):
        json_dic['exception'] = 'annotationIsReadOnly'
        # TODO: Display message here?
        display_message('Annotation is in read only mode', 'error')
        return json_dic


class DuplicateAnnotationIdError(Exception):
    def __init__(self, id):
        self.id = id

    def __str__(self):
        return 'Encountered a duplicate of id: %s' % (self.id, )


class InvalidIdError(Exception):
    def __init__(self, id):
        self.id = id
        
    def __str__(self):
        return 'Invalid id: %s' % (self.id, )


class DependingAnnotationDeleteError(Exception):
    def __init__(self, target, dependants):
        self.target = target
        self.dependants = dependants

    def __str__(self):
        return '%s can not be deleted due to depending annotations %s' % (
                self.target, ",".join([str(d) for d in self.dependants]))

    def html_error_str(self, response=None):
        return '''
        Annotation:
        <br/>
        %s
        <br/>
        Has depending annotations attached to it:
        <br/>
        %s
        ''' % (self.target, ",".join([str(d) for d in self.dependants]))


def __split_annotation_id(id):
    import re
    m = re.match(r'^([A-Za-z]|#)([0-9]+)(.*?)$', id)
    if m is None:
        raise InvalidIdError(id)
    pre, num_str, suf = m.groups()
    return pre, num_str, suf

def annotation_id_prefix(id):
    try:
        return id[0]
    except:
        raise InvalidIdError(id)

def annotation_id_number(id):
    return __split_annotation_id(id)[1]

# We are NOT concerned with the conformity to the text file
class Annotations(object):
    def get_document(self):
        return self._document

    #TODO: DOC!
    def __init__(self, document, read_only=False):
        #TODO: DOC!
        #TODO: Incorparate file locking! Is the destructor called upon inter crash?
        from collections import defaultdict
        from os.path import basename, isfile, getmtime, getctime
        from os import access, W_OK
        import fileinput

        # we should remember this
        self._document = document

        
        
        self.failed_lines = []

        ### Here be dragons, these objects need constant updating and syncing
        # Annotation for each line of the file
        self._lines = []
        # Mapping between annotation objects and which line they occur on
        # Range: [0, inf.) unlike [1, inf.) which is common for files
        self._line_by_ann = {}
        # Maximum id number used for each id prefix, to speed up id generation
        #XXX: This is effectively broken by the introduction of id suffixes
        self._max_id_num_by_prefix = defaultdict(lambda : 1)
        # Annotation by id, not includid non-ided annotations 
        self._ann_by_id = {}
        ###

        ## We use some heuristics to find the appropriate files
        self._read_only = read_only
        try:
            # Do we have a valid suffix? If so, it is probably best to the file
            suff = document[document.rindex('.') + 1:]
            if suff == JOINED_ANN_FILE_SUFF:
                # It is a joined file, let's load it
                input_files = [document]
                # Do we lack write permissions?
                if not access(document, W_OK):
                    #TODO: Should raise an exception or warning
                    self._read_only = True
            elif suff in PARTIAL_ANN_FILE_SUFF:
                # It is only a partial annotation, we will most likely fail
                # but we will try opening it
                input_files = [document]
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
                # Do we lack write permissions?
                if not access(sugg_path, W_OK):
                    #TODO: Should raise an exception or warning
                    self._read_only = True
            else:
                # Our last shot, we go for as many partial files as possible
                input_files = [sugg_path for sugg_path in 
                        (document + '.' + suff
                            for suff in PARTIAL_ANN_FILE_SUFF)
                        if isfile(sugg_path)]
                self._read_only = True

        # We then try to open the files we got using the heuristics
        if input_files:
            self._file_input = fileinput.input(input_files, mode='r')
            self._input_files = input_files
        else:
            #XXX: Proper exception here, this is horrible
            assert False, ('could not find any plausible annotations '
                    'for %s') % (document, )

        # Finally, parse the given annotation file
        self._parse_ann_file()

        #XXX: Hack to get the timestamps after parsing
        if (len(self._input_files) == 1 and
                self._input_files[0].endswith(JOINED_ANN_FILE_SUFF)):
            self.ann_mtime = getmtime(self._input_files[0])
            self.ann_ctime = getctime(self._input_files[0])
        else:
            # We don't have a single file, just set to epoch for now
            self.ann_mtime = 0
            self.ann_ctime = 0

    def get_events(self):
        return (a for a in self if isinstance(a, EventAnnotation))

    def get_equivs(self):
        return (a for a in self if isinstance(a, EquivAnnotation))

    def get_textbounds(self):
        return (a for a in self if isinstance(a, TextBoundAnnotation))

    def get_modifers(self):
        return (a for a in self if isinstance(a, ModifierAnnotation))

    def get_oneline_comments(self):
        #XXX: The status exception is for the document status protocol
        #       which is yet to be formalised
        return (a for a in self if isinstance(a, OnelineCommentAnnotation)
                and a.type != 'STATUS')

    def get_statuses(self):
        return (a for a in self if isinstance(a, OnelineCommentAnnotation)
                and a.type == 'STATUS')

    # TODO: getters for other categories of annotations
    #TODO: Remove read and use an internal and external version instead
    def add_annotation(self, ann, read=False):
        #TODO: DOC!
        #TODO: Check read only
        if not read and self._read_only:
            raise AnnotationsIsReadOnlyError

        # Equivs have to be merged with other equivs
        try:
            # Bail as soon as possible for non-equivs
            ann.entities # TODO: what is this?
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
            #XXX: This can catch a ton more than we want to! Ugly!
            # It was not an Equiv, skip along
            pass

        # Register the object id
        try:
            self._ann_by_id[ann.id] = ann
            pre, num = annotation_id_prefix(ann.id), annotation_id_number(ann.id)
            self._max_id_num_by_prefix[pre] = max(num, self._max_id_num_by_prefix[pre])
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
        #TODO: Check read only
        #TODO: Flag to allow recursion
        #TODO: Sampo wants to allow delet of direct deps but not indirect, one step
        #TODO: needed to pass tracker to track recursive mods, but use is too
        #      invasive (direct modification of ModificationTracker.deleted)
        #TODO: DOC!
        if self._read_only:
            raise AnnotationsIsReadOnlyError

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
              
        # If all depending are ModifierAnnotations or EquivAnnotations,
        # delete all modifiers recursively (without confirmation) and remove
        # the annotation id from the equivs (and remove the equiv if there is
        # only one id left in the equiv)
        # Note: this assumes ModifierAnnotations cannot have
        # other dependencies depending on them, nor can EquivAnnotations
        if all((False for d in ann_deps if (
            not isinstance(d, ModifierAnnotation)
            and not isinstance(d, EquivAnnotation)
            and not isinstance(d, OnelineCommentAnnotation)
            ))):

            for d in ann_deps:
                if isinstance(d, ModifierAnnotation):
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
                    #TODO: Can't anything refer to comments?
                    self._atomic_del_annotation(d)
                    if tracker is not None:
                        tracker.deletion(d)
            ann_deps = []
            
        if ann_deps:
            raise DependingAnnotationDeleteError(ann, ann_deps)

        if tracker is not None:
            tracker.deletion(ann)
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
        # Update the modification time
        from time import time
        self.ann_mtime = time()
    
    def get_ann_by_id(self, id):
        #TODO: DOC
        try:
            return self._ann_by_id[id]
        except KeyError:
            raise AnnotationNotFoundError(id)

    def get_new_id(self, prefix, suffix=None):
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
        #XXX: We have changed this one radically!
        #XXX: Stupid and linear
        if suffix is None:
            suffix = ''
        #XXX: Arbitary constant!
        for suggestion in (prefix + str(i) + suffix for i in xrange(1, 2**15)):
            # This is getting more complicated by the minute, two checks since
            # the developers no longer know when it is an id or string.
            if suggestion not in self._ann_by_id:
                return suggestion

    def _parse_ann_file(self):
        from itertools import takewhile
        # If you knew the format, you would have used regexes...
        #
        # We use ids internally since otherwise we need to resolve a dep graph
        # when parsing to make sure we have the annotations to refer to.

        #XXX: Assumptions start here...
        for ann_line_num, ann_line in enumerate(self._file_input):
            try:
                # ID processing
                try:
                    id, id_tail = ann_line.split('\t', 1)
                except ValueError:
                    raise AnnotationLineSyntaxError(ann_line, ann_line_num+1)

                pre = annotation_id_prefix(id)

                if id in self._ann_by_id and pre != '*':
                    raise DuplicateAnnotationIdError(id)

                # Cases for lines
                try:
                    data_delim = id_tail.index('\t')
                    data, data_tail = (id_tail[:data_delim],
                            id_tail[data_delim:])
                except ValueError:
                    data = id_tail
                    # No tail at all, although it should have a \t
                    data_tail = ''

                if pre == '*':
                    type, type_tail = data.split(None, 1)
                    # For now we can only handle Equivs
                    if type != 'Equiv':
                        raise AnnotationLineSyntaxError(ann_line, ann_line_num+1)
                    equivs = type_tail.split(None)
                    self.add_annotation(
                            EquivAnnotation(type, equivs, data_tail),
                            read=True)
                elif pre == 'E':
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
                        raise AnnotationLineSyntaxError(ann_line, ann_line_num+1)

                    if type_trigger_tail is not None:
                        args = [tuple(arg.split(':'))
                                for arg in type_trigger_tail.split()]
                    else:
                        args = []

                    self.add_annotation(EventAnnotation(
                        trigger, args, id, type, data_tail), read=True)
                elif pre == 'R':
                    raise NotImplementedError
                elif pre == 'M':
                    type, target = data.split()
                    self.add_annotation(ModifierAnnotation(
                        target, id, type, data_tail), read=True)
                elif pre == 'T' or pre == 'W':
                    type, start_str, end_str = data.split(None, 3)
                    # Abort if we have trailing values
                    if any((c.isspace() for c in end_str)):
                        raise AnnotationLineSyntaxError(ann_line, ann_line_num+1)
                    start, end = (int(start_str), int(end_str))
                    self.add_annotation(TextBoundAnnotation(
                        start, end, id, type, data_tail), read=True)
                elif pre == '#':
                    try:
                        type, target = data.split()
                    except ValueError:
                        raise AnnotationLineSyntaxError(ann_line, ann_line_num+1)
                    self.add_annotation(OnelineCommentAnnotation(
                        target, id, type, data_tail
                        ), read=True)
                else:
                    raise AnnotationLineSyntaxError(ann_line, ann_line_num+1)
            except AnnotationLineSyntaxError, e:
                # We could not parse the line, just add it as an unknown annotation
                self.add_annotation(Annotation(e.line), read=True)
                # NOTE: For access we start at line 0, not 1 as in here
                self.failed_lines.append(e.line_num - 1)

    def __str__(self):
        s = '\n'.join(str(ann).rstrip('\n') for ann in self)
        if not s:
            return ""
        else:
            return s if s[-1] == '\n' else s + '\n'

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
        self._file_input.close()
        if not self._read_only:
            assert len(self._input_files) == 1, 'more than one valid outfile'

            # We are hitting the disk a lot more than we should here, what we
            # should have is a modification flag in the object but we can't
            # due to how we change the annotations.
            
            out_str = str(self)
            with open(self._input_files[0], 'r') as old_ann_file:
                old_str = old_ann_file.read()

            # Was it changed?
            if out_str != old_str:
                from tempfile import NamedTemporaryFile
                # TODO: XXX: Is copyfile really atomic?
                from shutil import copyfile
                with NamedTemporaryFile('w', suffix='.ann') as tmp_file:
                    #XXX: Temporary hack to make sure we don't write corrupted
                    #       files, but the client will already have the version
                    #       at this stage leading to potential problems upon
                    #       the next change to the file.
                    tmp_file.write(out_str)
                    tmp_file.flush()

                    try:
                        with Annotations(tmp_file.name) as ann:
                            # Move the temporary file onto the old file
                            copyfile(tmp_file.name, self._input_files[0])
                            # As a matter of convention we adjust the modified
                            # time of the data dir when we write to it. This
                            # helps us to make back-ups
                            now = time()
                            #XXX: Disabled for now!
                            #utime(DATA_DIR, (now, now))
                    except Exception, e:
                        from message import display_message
                        import sys
                        print >> sys.stderr, "Here", e
                        display_message('ERROR: Could not write changes!<br/>%s' % e, 'error', -1)
        return

    def __in__(self, other):
        #XXX: You should do this one!
        pass

class Annotation(object):
    def __init__(self, tail):
        self.tail = tail

    def __str__(self):
        return self.tail

    def __repr__(self):
        return '%s("%s")' % (str(self.__class__), str(self))
    
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

    def reference_id(self):
        # Return list that uniquely identifies this annotation within the document
        return [self.id]

    def __str__(self):
        raise NotImplementedError


class EventAnnotation(IdedAnnotation):
    def __init__(self, trigger, args, id, type, tail):
        IdedAnnotation.__init__(self, id, type, tail)
        self.trigger = trigger
        self.args = args

    def __str__(self):
        return '%s\t%s:%s %s%s' % (
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
        return '*\t%s %s%s' % (
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

class ModifierAnnotation(IdedAnnotation):
    def __init__(self, target, id, type, tail):
        IdedAnnotation.__init__(self, id, type, tail)
        self.target = target
        
    def __str__(self):
        return '%s\t%s %s%s' % (
                self.id,
                self.type,
                self.target,
                self.tail
                )

    def get_deps(self):
        soft_deps, hard_deps = IdedAnnotation.get_deps(self)
        hard_deps.add(self.target)
        return (soft_deps, hard_deps)

    def reference_id(self):
        # TODO: can't currently ID modifier in isolation; return
        # reference to modified instead
        return [self.target]

class OnelineCommentAnnotation(IdedAnnotation):
    def __init__(self, target, id, type, tail):
        IdedAnnotation.__init__(self, id, type, tail)
        self.target = target
        
    def __str__(self):
        return '%s\t%s %s%s' % (
                self.id,
                self.type,
                self.target,
                self.tail
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
        return '%s\t%s %s %s%s' % (
                self.id,
                self.type,
                self.start,
                self.end,
                self.tail
                )

if __name__ == '__main__':
    #TODO: Unit-testing
    pass
