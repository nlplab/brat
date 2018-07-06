#!/usr/bin/env python

# "Normalizes" IDs in brat-flavored standoff so that the first "T" ID
# is "T1", the second "T2", and so on, for all ID prefixes.



import sys

DEBUG = True


class Annotation(object):
    def __init__(self, id_, type_):
        self.id_ = id_
        self.type_ = type_

    def map_ids(self, idmap):
        self.id_ = idmap[self.id_]


class Textbound(Annotation):
    def __init__(self, id_, type_, offsets, text):
        Annotation.__init__(self, id_, type_)
        self.offsets = offsets
        self.text = text

    def map_ids(self, idmap):
        Annotation.map_ids(self, idmap)

    def __str__(self):
        return "%s\t%s %s\t%s" % (self.id_, self.type_,
                                  ' '.join(self.offsets), self.text)


class ArgAnnotation(Annotation):
    def __init__(self, id_, type_, args):
        Annotation.__init__(self, id_, type_)
        self.args = args

    def map_ids(self, idmap):
        Annotation.map_ids(self, idmap)
        mapped = []
        for arg in self.args:
            key, value = arg.split(':')
            value = idmap[value]
            mapped.append("%s:%s" % (key, value))
        self.args = mapped


class Relation(ArgAnnotation):
    def __init__(self, id_, type_, args):
        ArgAnnotation.__init__(self, id_, type_, args)

    def map_ids(self, idmap):
        ArgAnnotation.map_ids(self, idmap)

    def __str__(self):
        return "%s\t%s %s" % (self.id_, self.type_, ' '.join(self.args))


class Event(ArgAnnotation):
    def __init__(self, id_, type_, trigger, args):
        ArgAnnotation.__init__(self, id_, type_, args)
        self.trigger = trigger

    def map_ids(self, idmap):
        ArgAnnotation.map_ids(self, idmap)
        self.trigger = idmap[self.trigger]

    def __str__(self):
        return "%s\t%s:%s %s" % (self.id_, self.type_, self.trigger,
                                 ' '.join(self.args))


class Attribute(Annotation):
    def __init__(self, id_, type_, target, value):
        Annotation.__init__(self, id_, type_)
        self.target = target
        self.value = value

    def map_ids(self, idmap):
        Annotation.map_ids(self, idmap)
        self.target = idmap[self.target]

    def __str__(self):
        return "%s\t%s %s%s" % (self.id_, self.type_, self.target,
                                '' if self.value is None else ' ' + self.value)


class Normalization(Annotation):
    def __init__(self, id_, type_, target, ref, reftext):
        Annotation.__init__(self, id_, type_)
        self.target = target
        self.ref = ref
        self.reftext = reftext

    def map_ids(self, idmap):
        Annotation.map_ids(self, idmap)
        self.target = idmap[self.target]

    def __str__(self):
        return "%s\t%s %s %s\t%s" % (self.id_, self.type_, self.target,
                                     self.ref, self.reftext)


class Equiv(Annotation):
    def __init__(self, id_, type_, targets):
        Annotation.__init__(self, id_, type_)
        self.targets = targets

    def map_ids(self, idmap):
        Annotation.map_ids(self, idmap)
        self.targets = [idmap[target] for target in self.targets]

    def __str__(self):
        return "%s\t%s %s" % (self.id_, self.type_, ' '.join(self.targets))


class Note(Annotation):
    def __init__(self, id_, type_, target, text):
        Annotation.__init__(self, id_, type_)
        self.target = target
        self.text = text

    def map_ids(self, idmap):
        Annotation.map_ids(self, idmap)
        self.target = idmap[self.target]

    def __str__(self):
        return "%s\t%s %s\t%s" % (self.id_, self.type_, self.target, self.text)


def parse_textbound(fields):
    id_, type_offsets, text = fields
    type_offsets = type_offsets.split(' ')
    type_, offsets = type_offsets[0], type_offsets[1:]
    return Textbound(id_, type_, offsets, text)


def parse_relation(fields):
    id_, type_args = fields
    type_args = type_args.split(' ')
    type_, args = type_args[0], type_args[1:]
    return Relation(id_, type_, args)


def parse_event(fields):
    id_, type_trigger_args = fields
    type_trigger_args = type_trigger_args.split(' ')
    type_trigger, args = type_trigger_args[0], type_trigger_args[1:]
    type_, trigger = type_trigger.split(':')
    # remove empty "arguments"
    args = [a for a in args if a]
    return Event(id_, type_, trigger, args)


def parse_attribute(fields):
    id_, type_target_value = fields
    type_target_value = type_target_value.split(' ')
    if len(type_target_value) == 3:
        type_, target, value = type_target_value
    else:
        type_, target = type_target_value
        value = None
    return Attribute(id_, type_, target, value)


def parse_normalization(fields):
    id_, type_target_ref, reftext = fields
    type_, target, ref = type_target_ref.split(' ')
    return Normalization(id_, type_, target, ref, reftext)


def parse_note(fields):
    id_, type_target, text = fields
    type_, target = type_target.split(' ')
    return Note(id_, type_, target, text)


def parse_equiv(fields):
    id_, type_targets = fields
    type_targets = type_targets.split(' ')
    type_, targets = type_targets[0], type_targets[1:]
    return Equiv(id_, type_, targets)


parse_func = {
    'T': parse_textbound,
    'R': parse_relation,
    'E': parse_event,
    'N': parse_normalization,
    'M': parse_attribute,
    'A': parse_attribute,
    '#': parse_note,
    '*': parse_equiv,
}


def parse(l, ln):
    assert len(l) and l[0] in parse_func, "Error on line %d: %s" % (ln, l)
    try:
        return parse_func[l[0]](l.split('\t'))
    except Exception:
        assert False, "Error on line %d: %s" % (ln, l)


def process(fn):
    idmap = {}

    with open(fn, "rU") as f:
        lines = [l.rstrip('\n') for l in f.readlines()]

        annotations = []
        for i, l in enumerate(lines):
            annotations.append(parse(l, i + 1))

        if DEBUG:
            for i, a in enumerate(annotations):
                assert lines[i] == str(a), ("Cross-check failed:\n  " +
                                            '"%s"' % lines[i] + " !=\n  " +
                                            '"%s"' % str(a))

        idmap = {}
        next_free = {}
        # special case: ID '*' maps to itself
        idmap['*'] = '*'
        for i, a in enumerate(annotations):
            if a.id_ == '*':
                continue
            assert a.id_ not in idmap, "Dup ID on line %d: %s" % (i, l)
            prefix = a.id_[0]
            seq = next_free.get(prefix, 1)
            idmap[a.id_] = prefix + str(seq)
            next_free[prefix] = seq + 1

        for i, a in enumerate(annotations):
            a.map_ids(idmap)
            print(a)


def main(argv):
    if len(argv) < 2:
        print("Usage:", argv[0], "FILE [FILE ...]", file=sys.stderr)
        return 1

    for fn in argv[1:]:
        process(fn)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
