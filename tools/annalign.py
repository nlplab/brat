#!/usr/bin/env python

# Align text and annotations to a different version of the same text.

# Note: not comprehensively tested, use with caution.


import codecs
import sys


DEFAULT_ENCODING = 'UTF-8'
TEST_ARG = '--test'

DEBUG = False

WARN_LENGTH_PRODUCT = 1000000

options = None


def argparser():
    import argparse

    ap = argparse.ArgumentParser(
        description="Align text and annotations to different version of same text.")
    ap.add_argument(TEST_ARG, default=False, action="store_true",
                    help="Perform self-test and exit")
    ap.add_argument('-e', '--encoding', default=DEFAULT_ENCODING,
                    help='text encoding (default %s)' % DEFAULT_ENCODING)
    ap.add_argument('-v', '--verbose', default=False, action="store_true",
                    help="Verbose output")
    ap.add_argument("ann", metavar="ANN", nargs=1,
                    help="Annotation file")
    ap.add_argument("oldtext", metavar="OLD-TEXT", nargs=1,
                    help="Text matching annotation")
    ap.add_argument("newtext", metavar="NEW-TEXT", nargs=1,
                    help="Text to align to")
    return ap


class Annotation(object):
    def __init__(self, id_, type_):
        self.id_ = id_
        self.type_ = type_

    def remap(self, _):
        # assume not text-bound: no-op
        return None

    def fragment(self, _):
        # assume not text-bound: no-op
        return None

    def retext(self, _):
        # assume not text-bound: no-op
        return None


def escape_tb_text(s):
    return s.replace('\n', '\\n')


def is_newline(c):
    # from http://stackoverflow.com/a/18325046
    return c in (
        '\u000A',    # LINE FEED
        '\u000B',    # VERTICAL TABULATION
        '\u000C',    # FORM FEED
        '\u000D',    # CARRIAGE RETURN
        '\u001C',    # FILE SEPARATOR
        '\u001D',    # GROUP SEPARATOR
        '\u001E',    # RECORD SEPARATOR
        '\u0085',    # NEXT LINE
        '\u2028',    # LINE SEPARATOR
        '\u2029'     # PARAGRAPH SEPARATOR
    )


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

    def remap(self, mapper):
        remapped = []
        for start, end in self.offsets:
            remapped.append(mapper.remap(start, end))
        self.offsets = remapped

    def fragment(self, text):
        # Remapping may create spans that extend over newlines, which
        # brat doesn't handle well. Break any such span into multiple
        # fragments that skip newlines.
        fragmented = []
        for start, end in self.offsets:
            while start < end:
                while start < end and is_newline(text[start]):
                    start += 1  # skip initial newlines
                fend = start
                while fend < end and not is_newline(text[fend]):
                    fend += 1  # find max sequence of non-newlines
                if fend > start:
                    fragmented.append((start, fend))
                start = fend

        # Switch to fragmented. Edge case: if offsets now only span
        # newlines, replace them with a single zero-length span at
        # the start of the first original span.
        if fragmented:
            self.offsets = fragmented
        else:
            self.offsets = [(self.offsets[0][0], self.offsets[0][0])]

    def retext(self, text):
        self.text = ' '.join(text[o[0]:o[1]] for o in self.offsets)
        if any(is_newline(c) for c in self.text):
            print('Warning: newline in text: %s' % self.text, file=sys.stderr)

    def __unicode__(self):
        return "%s\t%s %s\t%s" % (self.id_, self.type_,
                                   ';'.join(['%d %d' % (s, e)
                                             for s, e in self.offsets]),
                                   escape_tb_text(self.text))

    def __str__(self):
        return "%s\t%s %s\t%s" % (self.id_, self.type_,
                                  ';'.join(['%d %d' % (s, e)
                                            for s, e in self.offsets]),
                                  escape_tb_text(self.text))


class XMLElement(Textbound):
    def __init__(self, id_, type_, offsets, text, attributes):
        Textbound.__init__(self, id_, type_, offsets, text)
        self.attributes = attributes

    def __str__(self):
        return "%s\t%s %s\t%s\t%s" % (self.id_, self.type_,
                                      ';'.join(['%d %d' % (s, e)
                                                for s, e in self.offsets]),
                                      escape_tb_text(self.text),
                                      self.attributes)


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


def parse_xml(fields):
    id_, type_offsets, text, attributes = fields
    type_offsets = type_offsets.split(' ')
    type_, offsets = type_offsets[0], type_offsets[1:]
    return XMLElement(id_, type_, offsets, text, attributes)


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
    'X': parse_xml,
    '#': parse_note,
    '*': parse_equiv,
}


def parse(l, ln):
    assert len(l) and l[0] in parse_func, "Error on line %d: %s" % (ln, l)
    try:
        return parse_func[l[0]](l.split('\t'))
    except Exception:
        assert False, "Error on line %d: %s" % (ln, l)


def parseann(fn):
    global options

    annotations = []
    with codecs.open(fn, 'rU', encoding=options.encoding) as f:
        lines = [l.rstrip('\n') for l in f.readlines()]

        for i, l in enumerate(lines):
            annotations.append(parse(l, i + 1))
    return annotations


def sim(a, b):
    if a == b:
        return 10
    else:
        return -1000


def swcost(a, b, extend=False):
    if a == b:
        return 10
    elif b is None:
        # insert
        if not extend:
            return -10
        else:
            return -2
    elif a is None:
        # delete
        if not extend:
            return -10
        else:
            return -2
    else:
        # mismatch
        return -1000


def match_cost(a, b):
    if a == b:
        if a.isspace():
            # low reward for space matches to encourage space ins/del
            # to get nonspace matches
            return 1
        else:
            return 10
    else:
        if a.isspace() and b.isspace():
            # low cost for space-to-space mismatches
            return 0
        else:
            return -1000


def space_boundary(s, i):
    if (i == 0 or s[i - 1].isspace() != s[i].isspace() or
            i + 1 == len(s) or s[i + 1].isspace() != s[i].isspace()):
        return True
    else:
        return False


CH_OUT, CH_MATCH, CH_DELETE, CH_SPC_DELETE, CH_INSERT, CH_SPC_INSERT = list(range(6))


def delete_cost(A, B, i, j, choices):
    if choices[i - 1][j] == CH_DELETE:
        # standard gap extend
        return -1, CH_DELETE
    elif A[i - 1].isspace() and (B[j - 1].isspace() or space_boundary(B, j - 1)):
        # cheap space gap
        return -1, CH_SPC_DELETE
    elif space_boundary(B, j - 1) and space_boundary(A, i - 1):
        # boundary gap open
        return -5, CH_DELETE
    else:
        # standard gap open
        return -20, CH_DELETE


def insert_cost(A, B, i, j, choices):
    if choices[i][j - 1] == CH_INSERT:
        return -1, CH_INSERT
    elif B[j - 1].isspace() and (A[i - 1].isspace() or space_boundary(A, i - 1)):
        return -1, CH_SPC_INSERT
    elif space_boundary(A, i - 1) and space_boundary(B, j - 1):
        return -5, CH_INSERT
    else:
        return -10, CH_INSERT


def swchoice(A, B, i, j, F, choices):
    a, b = A[i - 1], B[j - 1]

    match = F[i - 1][j - 1] + match_cost(a, b)

    del_cost, del_choice = delete_cost(A, B, i, j, choices)
    delete = F[i - 1][j] + del_cost

    ins_cost, ins_choice = insert_cost(A, B, i, j, choices)
    insert = F[i][j - 1] + ins_cost

    best = max(match, delete, insert, 0)

    if best == match:
        choice = CH_MATCH
        if DEBUG and A[i - 1] != B[j - 1]:
            print("MISMATCH! '%s' vs '%s'" % (
                A[i - 1], B[j - 1]), file=sys.stderr)
    elif best == delete:
        choice = del_choice
    elif best == insert:
        choice = ins_choice
    else:
        assert best == 0
        choice = CH_OUT

    return best, choice


def smithwaterman(A, B, cost=swcost, as_str=False, align_full_A=True):
    """
    >>> smithwaterman('Simple', ' Simple ', as_str=True)
    ('-Simple-', ' Simple ')

    >>> smithwaterman('space is     cheap', 'space     is cheap', as_str=True)
    ('space---- is     cheap', 'space     is---- cheap')

    >>> smithwaterman('Gaps by space', 'Gaps bbyy space', as_str=True)
    ('Gaps -by- space', 'Gaps bbyy space')

    >>> smithwaterman('Gaps bbyy space', 'Gaps by space', as_str=True)
    ('Gaps bbyy space', 'Gaps -by- space')
    """

    global options

    rows = len(A) + 1
    cols = len(B) + 1

    F = [[0] * cols for _ in range(rows)]
    choices = [[0] * cols for _ in range(rows)]
    #F = numpy.zeros((rows, cols), int)

    maxs, maxi, maxj = 0, 0, 0
    for i in range(1, rows):
        for j in range(1, cols):
            F[i][j], choices[i][j] = swchoice(A, B, i, j, F, choices)
            if F[i][j] >= maxs:
                maxs, maxi, maxj = F[i][j], i, j

    # Note: this is an experimental modification of the basic
    # Smith-Waterman algorithm to provide an alignment for the whole
    # string A. The reason is to avoid cases where the local alignment
    # would drop trailing material when matching them required the
    # introduction of a long string of inserts, so that e.g. the
    # strings 'AB C' and 'AB ....... C' would align as 'AB ---------C'
    # and 'AB ....... C-' (where "-" denotes insert or delete). This
    # doesn't account for initial inserts, and is likely not a good
    # solution for trailing ones either.
    if align_full_A:
        # Force the choice of the best score to look only in the
        # subset of alternatives where the entire string A is
        # processed.
        maxs, maxi, maxj = 0, 0, 0
        i = rows - 1
        for j in range(1, cols):
            if F[i][j] >= maxs:
                maxs, maxi, maxj = F[i][j], i, j

    alignA, alignB = [], []

    i = rows - 1
    j = cols - 1

    while i > maxi:
        alignA.insert(0, A[i - 1])
        alignB.insert(0, None)
        i -= 1
    while j > maxj:
        alignA.insert(0, None)
        alignB.insert(0, B[j - 1])
        j -= 1

    while i > 0 and j > 0 and F[i][j] > 0:
        if choices[i][j] == CH_MATCH:
            if options and options.verbose or DEBUG:
                print('match : "%s"-"%s" (%d)' % \
                    (A[i - 1], B[j - 1], F[i][j]), file=sys.stderr)
            alignA.insert(0, A[i - 1])
            alignB.insert(0, B[j - 1])
            i -= 1
            j -= 1
        elif choices[i][j] in (CH_DELETE, CH_SPC_DELETE):
            if options and options.verbose or DEBUG:
                print('delete: "%s" (%d)' % (A[i - 1], F[i][j]), file=sys.stderr)
            alignA.insert(0, A[i - 1])
            alignB.insert(0, None)
            i -= 1
        elif choices[i][j] in (CH_INSERT, CH_SPC_INSERT):
            if options and options.verbose or DEBUG:
                print('insert: "%s" (%d)' % (B[j - 1], F[i][j]), file=sys.stderr)
            alignA.insert(0, None)
            alignB.insert(0, B[j - 1])
            j -= 1
        else:
            assert False, 'internal error'

    while i > 0:
        alignA.insert(0, A[i - 1])
        alignB.insert(0, None)
        i -= 1
    while j > 0:
        alignA.insert(0, None)
        alignB.insert(0, B[j - 1])
        j -= 1

    # sanity
    assert A == ''.join([a for a in alignA if a is not None])
    assert B == ''.join([b for b in alignB if b is not None])

    if as_str:
        alignA = ''.join([a if a is not None else '-' for a in alignA])
        alignB = ''.join([b if b is not None else '-' for b in alignB])

    return alignA, alignB


def needlemanwunsch(A, B, gap_penalty=-5):
    rows = len(A) + 1
    cols = len(B) + 1

    F = [[0] * cols for i in range(rows)]
    #F = numpy.zeros((rows, cols), int)

    for i in range(rows):
        F[i][0] = i * gap_penalty
    for j in range(cols):
        F[0][j] = j * gap_penalty

    for i in range(1, rows):
        for j in range(1, cols):
            match = F[i - 1][j - 1] + sim(A[i - 1], B[j - 1])
            delete = F[i - 1][j] + gap_penalty
            insert = F[i][j - 1] + gap_penalty
            F[i][j] = max(match, delete, insert)

    i = rows - 1
    j = cols - 1
    alignA, alignB = [], []
    while i > 0 and j > 0:
        if F[i][j] == F[i - 1][j - 1] + sim(A[i - 1], B[j - 1]):
            # match
            alignA.insert(0, A[i - 1])
            alignB.insert(0, B[j - 1])
            i -= 1
            j -= 1
        elif F[i][j] == F[i - 1][j] + gap_penalty:
            # delete
            alignA.insert(0, A[i - 1])
            alignB.insert(0, None)
            i -= 1
        elif F[i][j] == F[i][j - 1] + gap_penalty:
            # insert
            alignA.insert(0, None)
            alignB.insert(0, B[j - 1])
            j -= 1
        else:
            assert False, 'internal error'

    while i > 0:
        alignA.insert(0, A[i - 1])
        alignB.insert(0, None)
        i -= 1
    while j > 0:
        alignA.insert(0, None)
        alignB.insert(0, B[j - 1])
        j -= 1

    # sanity
    assert A == ''.join([a for a in alignA if a is not None])
    assert B == ''.join([b for b in alignB if b is not None])

    return F[-1][-1]


class CannotSpaceAlign(Exception):
    pass


def spacealign(A, B, as_str=False):
    """
    >>> spacealign('Simple', ' Simple ', as_str=True)
    ('-Simple-', ' Simple ')

    >>> spacealign(' Simple ', 'Simple', as_str=True)
    (' Simple ', '-Simple-')
    """

    As = ''.join([c for c in A if not c.isspace()])
    Bs = ''.join([c for c in B if not c.isspace()])

    # TODO: substrings could also easily be covered here
    if As != Bs:
        raise CannotSpaceAlign

    i, j, alignA, alignB = 0, 0, [], []
    while i < len(A) and j < len(B):
        if A[i] == B[j]:
            alignA.append(A[i])
            alignB.append(B[j])
            i += 1
            j += 1
        elif A[i].isspace():
            alignA.append(A[i])
            alignB.append(None)
            i += 1
        elif B[j].isspace():
            alignA.append(None)
            alignB.append(B[j])
            j += 1
        else:
            assert False, 'internal error'

    while i < len(A):
        alignA.append(A[i])
        alignB.append(None)
        i += 1
    while j < len(B):
        alignA.append(None)
        alignB.append(B[j])
        j += 1

    # sanity
    newA = ''.join([a for a in alignA if a is not None])
    newB = ''.join([b for b in alignB if b is not None])
    assert A == newA, 'spacealign mismatch: "{}" vs "{}"'.format(A, newA)
    assert B == newB, 'spacealign mismatch: "{}" vs "{}"'.format(B, newB)

    if as_str:
        alignA = ''.join([a if a is not None else '-' for a in alignA])
        alignB = ''.join([b if b is not None else '-' for b in alignB])

    return (alignA, alignB)


def align(text1, text2):
    # Smith-Waterman is O(nm) in memory and time and will fail for
    # large inputs. As differences in space only represent a common
    # special case that can be resolved in O(n+m), try this first.
    try:
        a, b = spacealign(text1, text2)
    except CannotSpaceAlign:
        if len(text1) * len(text2) > WARN_LENGTH_PRODUCT:
            print('Warning: running Smith-Waterman on long' \
                ' texts, O(nm) in memory and time.', file=sys.stderr)
        a, b = smithwaterman(text1, text2)

    # create offset map from text1 to text2
    offset_map = []
    o = 0
    for i in range(len(a)):
        if a[i] is not None:
            if b[i] is not None:
                offset_map.append(o)
                o += 1
            else:
                offset_map.append(o)
        else:
            assert b[i] is not None, 'internal error'
            o += 1

    assert len(offset_map) == len(text1)
    return offset_map


class Remapper(object):
    def __init__(self, offset_map):
        self.offset_map = offset_map

    def remap(self, start, end):
        if start == end:
            return offset_map[start], offset_map[end]
        else:
            return self.offset_map[start], self.offset_map[end - 1] + 1


def test():
    import doctest
    doctest.testmod()


def main(argv=None):
    global options

    if argv is None:
        argv = sys.argv

    if TEST_ARG in argv:
        test()
        return 0
    options = argparser().parse_args(argv[1:])

    annotations = parseann(options.ann[0])

    with codecs.open(options.oldtext[0], 'rU', encoding=options.encoding) as f:
        oldtext = f.read()
    with codecs.open(options.newtext[0], 'rU', encoding=options.encoding) as f:
        newtext = f.read()

    offset_map = align(oldtext, newtext)

    for a in annotations:
        a.remap(Remapper(offset_map))
        a.fragment(newtext)
        a.retext(newtext)
        print(a)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
