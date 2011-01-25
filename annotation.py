'''
Functionality related to the annotation file format.

Author:     Pontus Stenetorp   <pontus is s u tokyo ac jp>
Version:    2010-01-25
'''

#TODO: Rename and re-work this one
class AnnotationLineSyntaxError(Exception):
    def __init__(self, line, line_num):
        self.line = line
        self.line_num = line_num

    def __str__(self):
        'Syntax error on line {}: "{}"'.format(line_num, line)


class AnnotationNotFoundError(Exception):
    def __init__(self, id):
        self.id = id

    def __str__(self):
        return 'Could not find an annotation with id: {}'.format(self.id)


class DuplicateAnnotationIdError(Exception):
    def __init__(self, id):
        self.id = id

    def __str__(self):
        return 'Encountered a duplicate of id: {}'.format(self.id)


class InvalidIdError(Exception):
    def __init__(self, id):
        self.id = id
        
    def __str__(self):
        return 'Invalid id: {}'.format(self.id)



class DependingAnnotationDeleteError(Exception):
    def __init__(self, target, dependant):
        self.target = target
        self.dependant = dependant

    def __str__(self):
        return '{} can not be deleted due to depending annotation {}'.format(
                self.target, self.dependant)

    def json_error_response(self, response=None):
        if response is None:
            response = {}
        response['error'] = '''
        Annotation:
        <br/>
        {}
        <br/>
        Has a depending annotation attached to it:
        <br/>
        {}
        '''.format(self.target, self.dependant)
        return response


class AnnotationId(object):
    '''
    ^([A-Za-z]|#)[0-9]+(.*?)$
    '''
    def __init__(self, id_str):
        import re
        m = re.match(r'^([A-Za-z]|#)([0-9]+)(.*?)$', id_str)
        if m is None:
            raise InvalidIdError(id)

        self.pre, num_str, self.suf = m.groups()
        # Should never fail if the regex holds
        self.num = int(num_str)

    def __hash__(self):
        return hash(self.pre) + hash(self.num) + hash(self.suf)

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __cmp__(self, other):
        return cmp(hash(self), hash(other))

    def __str__(self):
        return '{}{}{}'.format(self.pre, self.num, self.suf)

    def __repr__(self):
        return str(self)


# We are NOT concerned with the conformity to the text file
class Annotations(object):
    #TODO: DOC!
    #TODO: We should handle ID collisions somehow upon initialisation
    def __init__(self, ann_iter):
        #TODO: DOC!
        #TODO: Incorparate file locking! Is the destructor called upon inter crash?
        from collections import defaultdict
        
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

    def get_oneline_comments(self):
        return (a for a in self if isinstance(a, OnelineCommentAnnotation))

    # TODO: getters for other categories of annotations

    def add_annotation(self, ann):
        #TODO: DOC!
        
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
                                        'never have dependents')
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
            self._ann_by_id[ann.id] = ann
            self._max_id_num_by_prefix[ann.id.pre] = max(ann.id.num, 
                    self._max_id_num_by_prefix[ann.id.pre])
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
                raise DependingAnnotationDeleteError(ann, other_ann)
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
        # support access by string
        if isinstance(id, str):
            id = AnnotationId(id)
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
        for ann_line_num, ann_line in enumerate(ann_iter, start=1):
            try:
                # ID processing
                try:
                    id_str, id_tail = ann_line.split('\t', 1)
                except ValueError:
                    raise AnnotationLineSyntaxError(ann_line, ann_line_num)

                try:
                    id = AnnotationId(id_str)
                except InvalidIdError:
                    # The line lacks an id, we attempt to create a dummy
                    from collections import namedtuple
                    id =  namedtuple('DummyId', ('pre', 'num', 'suf')
                            )(id_str, None, None)

                if id in self._ann_by_id:
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

                if id.pre == '*':
                    type, type_tail = data.split(None, 1)
                    # For now we can only handle Equivs
                    if type != 'Equiv':
                        raise AnnotationLineSyntaxError(ann_line, ann_line_num)
                    equivs = type_tail.split(None)
                    self.add_annotation(
                            EquivAnnotation(type, equivs, data_tail))
                elif id.pre == 'E':
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
                        raise AnnotationLineSyntaxError(ann_line, ann_line_num)

                    #if type_trigger_tail == ' ':
                    #    args = []
                    if type_trigger_tail is not None:
                        args = [tuple(arg.split(':'))
                                for arg in type_trigger_tail.split()]
                    else:
                        args = []

                    self.add_annotation(EventAnnotation(
                        trigger, args, id, type, data_tail))
                elif id.pre == 'R':
                    raise NotImplementedError
                elif id.pre == 'M':
                    type, target = data.split()
                    self.add_annotation(ModifierAnnotation(
                        target, id, type, data_tail))
                elif id.pre == 'T' or id.pre == 'W':
                    type, start_str, end_str = data.split(None, 3)
                    # Abort if we have trailing values
                    if any((c.isspace() for c in end_str)):
                        raise AnnotationLineSyntaxError(ann_line, ann_line_num)
                    start, end = (int(start_str), int(end_str))
                    #txt_file.seek(start)
                    #text = txt_file.read(end - start)
                    self.add_annotation(TextBoundAnnotation(
                        start, end, id, type, data_tail))
                elif id.pre == '#':
                    type, target = data.split()
                    self.add_annotation(OnelineCommentAnnotation(
                        target, id, type, data_tail
                        ))
                else:
                    #assert False, ann_line #XXX: REMOVE!
                    raise AnnotationLineSyntaxError(ann_line, ann_line_num)
                    #assert False, 'No code to handle exception type'
            except AnnotationLineSyntaxError, e:
                # We could not parse the line, just add it as an unknown annotation
                self.add_annotation(Annotation(e.line))
                # NOTE: For access we start at line 0, not 1 as in here
                self.failed_lines.append(e.line_num - 1)

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

class Annotation(object):
    def __init__(self, tail):
        self.tail = tail

    def __str__(self):
        return self.tail

    def __repr__(self):
        return str(self)
    
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
                args=' '.join([':'.join(map(str, arg_tup))
                    for arg_tup in self.args]),
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
                equivs=' '.join([str(e) for e in self.entities]),
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
        hard_deps.add(AnnotationId(self.target))
        return (soft_deps, hard_deps)


class OnelineCommentAnnotation(IdedAnnotation):
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

if __name__ == '__main__':
    #TODO: Unit-testing
    pass
