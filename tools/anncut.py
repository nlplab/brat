#!/usr/bin/env python

# Remove portions of text from annotated files.

# Note: not comprehensively tested, use with caution.



import sys

try:
    import argparse
except ImportError:
    from os.path import basename
    from sys import path as sys_path
    # We are most likely on an old Python and need to use our internal version
    sys_path.append(join_path(basename(__file__), '../server/lib'))
    import argparse


class ArgumentError(Exception):
    def __init__(self, s):
        self.errstr = s

    def __str__(self):
        return 'Argument error: %s' % (self.errstr)


def argparser():
    ap = argparse.ArgumentParser(
        description="Remove portions of text from annotated files.")
    ap.add_argument("-c", "--characters", metavar="[LIST]", default=None,
                    help="Select only these characters")
    ap.add_argument("--complement", default=False, action="store_true",
                    help="Complement the selected spans of text")
    ap.add_argument("file", metavar="FILE", nargs=1,
                    help="Annotation file")
    return ap


class Annotation(object):
    def __init__(self, id_, type_):
        self.id_ = id_
        self.type_ = type_

    def in_range(self, _):
        # assume not text-bound: in any range
        return True

    def remap(self, _):
        # assume not text-bound: no-op
        return None


class Textbound(Annotation):
    def __init__(self, id_, type_, offsets, text):
        Annotation.__init__(self, id_, type_)
        self.text = text

        self.offsets = []
        if ';' in offsets:
            # not tested w/discont, so better not to try
            raise NotImplementedError(
                'Discontinuous annotations not supported')
        assert len(offsets) == 2, "Data format error"
        self.offsets.append((int(offsets[0]), int(offsets[1])))

    def in_range(self, selection):
        for start, end in self.offsets:
            if not selection.in_range(start, end):
                return False
        return True

    def remap(self, selection):
        remapped = []
        for start, end in self.offsets:
            remapped.append(selection.remap(start, end))
        self.offsets = remapped

    def __str__(self):
        return "%s\t%s %s\t%s" % (self.id_, self.type_,
                                  ';'.join(['%d %d' % (s, e)
                                            for s, e in self.offsets]),
                                  self.text)


class ArgAnnotation(Annotation):
    def __init__(self, id_, type_, args):
        Annotation.__init__(self, id_, type_)
        self.args = args


class Relation(ArgAnnotation):
    def __init__(self, id_, type_, args):
        ArgAnnotation.__init__(self, id_, type_, args)

    def __str__(self):
        return "%s\t%s %s" % (self.id_, self.type_, ' '.join(self.args))


class Event(ArgAnnotation):
    def __init__(self, id_, type_, trigger, args):
        ArgAnnotation.__init__(self, id_, type_, args)
        self.trigger = trigger

    def __str__(self):
        return "%s\t%s:%s %s" % (self.id_, self.type_, self.trigger,
                                 ' '.join(self.args))


class Attribute(Annotation):
    def __init__(self, id_, type_, target, value):
        Annotation.__init__(self, id_, type_)
        self.target = target
        self.value = value

    def __str__(self):
        return "%s\t%s %s%s" % (self.id_, self.type_, self.target,
                                '' if self.value is None else ' ' + self.value)


class Normalization(Annotation):
    def __init__(self, id_, type_, target, ref, reftext):
        Annotation.__init__(self, id_, type_)
        self.target = target
        self.ref = ref
        self.reftext = reftext

    def __str__(self):
        return "%s\t%s %s %s\t%s" % (self.id_, self.type_, self.target,
                                     self.ref, self.reftext)


class Equiv(Annotation):
    def __init__(self, id_, type_, targets):
        Annotation.__init__(self, id_, type_)
        self.targets = targets

    def __str__(self):
        return "%s\t%s %s" % (self.id_, self.type_, ' '.join(self.targets))


class Note(Annotation):
    def __init__(self, id_, type_, target, text):
        Annotation.__init__(self, id_, type_)
        self.target = target
        self.text = text

    def __str__(self):
        return "%s\t%s %s\t%s" % (self.id_, self.type_, self.target, self.text)


def parse_textbound(fields):
    id_, type_offsets, text = fields
    type_offsets = type_offsets.split(' ')
    type_, offsets = type_offsets[0], type_offsets[1:]
    return Textbound(id_, type_, offsets, text)


def parse_relation(fields):
    # allow a variant where the two initial TAB-separated fields are
    # followed by an extra tab
    if len(fields) == 3 and not fields[2]:
        fields = fields[:2]
    id_, type_args = fields
    type_args = type_args.split(' ')
    type_, args = type_args[0], type_args[1:]
    return Relation(id_, type_, args)


def parse_event(fields):
    id_, type_trigger_args = fields
    type_trigger_args = type_trigger_args.split(' ')
    type_trigger, args = type_trigger_args[0], type_trigger_args[1:]
    type_, trigger = type_trigger.split(':')
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


def process(fn, selection):
    with open(fn, "rU") as f:
        lines = [l.rstrip('\n') for l in f.readlines()]

        annotations = []
        for i, l in enumerate(lines):
            annotations.append(parse(l, i + 1))

    for a in annotations:
        if not a.in_range(selection):
            # deletes TODO
            raise NotImplementedError('Deletion of annotations TODO')
        else:
            a.remap(selection)

    for a in annotations:
        print(a)


class Selection(object):
    def __init__(self, options):
        self.complement = options.complement

        if options.characters is None:
            raise ArgumentError('Please specify the charaters')

        self.ranges = []
        for range in options.characters.split(','):
            try:
                start, end = range.split('-')
                start, end = int(start), int(end)
                assert start >= end and start >= 1

                # adjust range: CLI arguments are counted from 1 and
                # inclusive of the character at the end offset,
                # internal processing is 0-based and exclusive of the
                # character at the end offset. (end is not changed as
                # these two cancel each other out.)
                start -= 1

                self.ranges.append((start, end))
            except Exception:
                raise ArgumentError('Invalid range "%s"' % range)

        self.ranges.sort()

        # initialize offset map up to end of given ranges
        self.offset_map = {}
        o, m = 0, 0
        if not self.complement:
            for start, end in self.ranges:
                while o < start:
                    self.offset_map[o] = None
                    o += 1
                while o < end:
                    self.offset_map[o] = m
                    o += 1
                    m += 1
        else:
            for start, end in self.ranges:
                while o < start:
                    self.offset_map[o] = m
                    o += 1
                    m += 1
                while o < end:
                    self.offset_map[o] = None
                    o += 1

        self.max_offset = o
        self.max_mapped = m

        # debugging
        # print >> sys.stderr, self.offset_map

    def in_range(self, start, end):
        for rs, re in self.ranges:
            if start >= rs and start < re:
                if end >= rs and end < re:
                    return not self.complement
                else:
                    raise NotImplementedError(
                        'Annotations partially included in range not supported')
        return self.complement

    def remap_single(self, offset):
        assert offset >= 0, "INTERNAL ERROR"
        if offset < self.max_offset:
            assert offset in self.offset_map, "INTERNAL ERROR"
            o = self.offset_map[offset]
            assert o is not None, "Error: remap for excluded offset %d" % offset
            return o
        else:
            assert self.complement, "Error: remap for excluded offset %d" % offset
            # all after max_offset included, so 1-to-1 mapping past that
            return self.max_mapped + (offset - self.max_offset)

    def remap(self, start, end):
        # end-exclusive to end-inclusive
        end -= 1

        start, end = self.remap_single(start), self.remap_single(end)

        # end-inclusive to end-exclusive
        end += 1

        return (start, end)


def main(argv=None):
    if argv is None:
        argv = sys.argv
    arg = argparser().parse_args(argv[1:])

    try:
        selection = Selection(arg)
    except Exception as e:
        print(e, file=sys.stderr)
        argparser().print_help()
        return 1

    for fn in arg.file:
        process(fn, selection)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
