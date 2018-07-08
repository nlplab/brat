#!/usr/bin/env python

# Script to revise the whitespace content of a PMC NXML file for text
# content extraction.



import os
import re
import sys

# TODO: switch to lxml
try:
    import xml.etree.ElementTree as ET
except ImportError:
    import cElementTree as ET

# TODO: the model of "space wrap" is unnecessarily crude in many
# cases. For example, for <issue> we would ideally want to have
# "<issue>1</issue><title>Foo</title>" spaced as "1 Foo" but
# "<issue>1</issue>: <page>100</page>" spaced as "1: 100".  This could
# be addressed by differentiating between things that should be
# wrapped by space in all cases and ones where it's only needed
# at non-word-boundaries (\b).

# tag to use for inserted elements
INSERTED_ELEMENT_TAG = "n2t-spc"

INPUT_ENCODING = "UTF-8"
OUTPUT_ENCODING = "UTF-8"

# command-line options
options = None

newline_wrap_element = set([
    "CURRENT_TITLE",

    "CURRENT_AUTHORLIST",

    "ABSTRACT",
    "P",

    "TABLE",
    "FIGURE",

    "HEADER",

    "REFERENCE",

    "article-title",
    "abstract",
    "title",
    "sec",
    "p",
    "contrib",   # contributor (author list)
    "aff",       # affiliation
    "pub-date",  # publication date
    "copyright-statement",
    "table",
    "table-wrap",
    "figure",
    "fig",       # figure (alternate)
    "tr",        # table row
    "kwd-group",  # keyword group
])

space_wrap_element = set([
    "AUTHOR",
    "SURNAME",

    "CURRENT_AUTHOR",
    "CURRENT_SURNAME",

    "TITLE",
    "JOURNAL",

    "YEAR",

    # author lists
    "surname",
    "given-names",
    "email",
    # citation details
    "volume",
    "issue",
    "year",
    "month",
    "day",
    "fpage",
    "lpage",
    "pub-id",
    "copyright-year",
    # journal meta
    "journal-id",
    "journal-title",
    "issn",
    "publisher-name",
    # article meta
    "article-id",
    "kwd",  # keyword
    # miscellaneous
    "label",
    "th",
    "td",
])

# strip anything that we're wrapping; this is a bit unnecessarily
# aggressive in cases but guarantees normalization
strip_element = newline_wrap_element | space_wrap_element


class Standoff:
    def __init__(self, element, start, end):
        self.element = element
        self.start = start
        self.end = end


def txt(s):
    return s if s is not None else ""


def text_and_standoffs(e):
    strings, standoffs = [], []
    _text_and_standoffs(e, 0, strings, standoffs)
    text = "".join(strings)
    return text, standoffs


def _text_and_standoffs(e, curroff, strings, standoffs):
    startoff = curroff
    # to keep standoffs in element occurrence order, append
    # a placeholder before recursing
    so = Standoff(e, 0, 0)
    standoffs.append(so)
    if e.text is not None and e.text != "":
        strings.append(e.text)
        curroff += len(e.text)
    curroff = _subelem_text_and_standoffs(e, curroff, strings, standoffs)
    so.start = startoff
    so.end = curroff
    return curroff


def _subelem_text_and_standoffs(e, curroff, strings, standoffs):
    for s in e:
        curroff = _text_and_standoffs(s, curroff, strings, standoffs)
        if s.tail is not None and s.tail != "":
            strings.append(s.tail)
            curroff += len(s.tail)
    return curroff


def preceding_space(pos, text, rewritten={}):
    while pos > 0:
        pos -= 1
        if pos not in rewritten:
            # no rewrite, check normally
            return text[pos].isspace()
        elif rewritten[pos] is not None:
            # refer to rewritten instead of original
            return rewritten[pos].isspace()
        else:
            # character deleted, ignore position
            pass
    # accept start of text
    return True


def following_space(pos, text, rewritten={}):
    while pos < len(text):
        if pos not in rewritten:
            # no rewrite, check normally
            return text[pos].isspace()
        elif rewritten[pos] is not None:
            # refer to rewritten instead of original
            return rewritten[pos].isspace()
        else:
            # character deleted, ignore position
            pass
        pos += 1
    # accept end of text
    return True


def preceding_linebreak(pos, text, rewritten={}):
    if pos >= len(text):
        return True
    while pos > 0:
        pos -= 1
        c = rewritten.get(pos, text[pos])
        if c == "\n":
            return True
        elif c is not None and not c.isspace():
            return False
        else:
            # space or deleted, check further
            pass
    return True


def following_linebreak(pos, text, rewritten={}):
    while pos < len(text):
        c = rewritten.get(pos, text[pos])
        if c == "\n":
            return True
        elif c is not None and not c.isspace():
            return False
        else:
            # space or deleted, check further
            pass
        pos += 1
    return True


def index_in_parent(e, p):
    """Returns the index of the given element in its parent element e."""
    for i in range(len(p)):
        if p[i] == e:
            break
    assert i is not None, "index_in_parent: error: not parent and child"
    return i


def space_normalize(root, text=None, standoffs=None):
    """Eliminates multiple consequtive spaces and normalizes newlines (and
    other space) into regular space."""

    if text is None or standoffs is None:
        text, standoffs = text_and_standoffs(root)

    # TODO: this is crude and destructive; improve!
    for so in standoffs:
        e = so.element
        if e.text is not None and e.text != "":
            e.text = re.sub(r'\s+', ' ', e.text)
        if e.tail is not None and e.tail != "":
            e.tail = re.sub(r'\s+', ' ', e.tail)


def strip_elements(root, elements_to_strip=set(), text=None, standoffs=None):
    """Removes initial and terminal space from elements that either have
    surrounding space or belong to given set of elements to strip."""

    if text is None or standoffs is None:
        text, standoffs = text_and_standoffs(root)

    # during processing, keep note at which offsets spaces have
    # been eliminated.
    rewritten = {}

    for so in standoffs:
        e = so.element

        # don't remove expressly inserted space
        if e.tag == INSERTED_ELEMENT_TAG:
            continue

        # if the element contains initial space and is either marked
        # for space stripping or preceded by space, remove the initial
        # space.
        if ((e.text is not None and e.text != "" and e.text[0].isspace()) and
            (element_in_set(e, elements_to_strip) or
             preceding_space(so.start, text, rewritten))):
            l = 0
            while l < len(e.text) and e.text[l].isspace():
                l += 1
            space, end = e.text[:l], e.text[l:]
            for i in range(l):
                assert so.start + \
                    i not in rewritten, "ERROR: dup remove at %d" % (so.start + i)
                rewritten[so.start + i] = None
            e.text = end

        # element-final space is in e.text only if the element has no
        # children; if it does, the element-final space is found in
        # the tail of the last child.
        if len(e) == 0:
            if ((e.text is not None and e.text != "" and e.text[-1].isspace()) and
                (element_in_set(e, elements_to_strip) or
                 following_space(so.end, text, rewritten))):
                l = 0
                while l < len(e.text) and e.text[-l - 1].isspace():
                    l += 1
                start, space = e.text[:-l], e.text[-l:]
                for i in range(l):
                    o = so.end - i - 1
                    assert o not in rewritten, "ERROR: dup remove"
                    rewritten[o] = None
                e.text = start

        else:
            c = e[-1]
            if ((c.tail is not None and c.tail != "" and c.tail[-1].isspace()) and
                (element_in_set(e, elements_to_strip) or
                 following_space(so.end, text, rewritten))):
                l = 0
                while l < len(c.tail) and c.tail[-l - 1].isspace():
                    l += 1
                start, space = c.tail[:-l], c.tail[-l:]
                for i in range(l):
                    o = so.end - i - 1
                    assert o not in rewritten, "ERROR: dup remove"
                    rewritten[o] = None
                c.tail = start


def trim_tails(root):
    """Trims the beginning of the tail of elements where it is preceded by
    space."""

    # This function is primarily necessary to cover the special case
    # of empty elements preceded and followed by space, as the
    # consecutive spaces created by such elements are not accessible
    # to the normal text content-stripping functionality.

    # work with standoffs for reference
    text, standoffs = text_and_standoffs(root)

    for so in standoffs:
        e = so.element

        if (e.tail is not None and e.tail != "" and e.tail[0].isspace() and
                preceding_space(so.end, text)):
            l = 0
            while l < len(e.tail) and e.tail[l].isspace():
                l += 1
            space, end = e.tail[:l], e.tail[l:]
            e.tail = end


def reduce_space(root, elements_to_strip=set()):
    """Performs space-removing normalizations."""

    # convert tree into text and standoffs for reference
    text, standoffs = text_and_standoffs(root)

    strip_elements(root, elements_to_strip, text, standoffs)

    trim_tails(root)

    space_normalize(root, text, standoffs)


def element_in_set(e, s):
    # strip namespaces for lookup
    if e.tag[0] == "{":
        tag = re.sub(r'\{.*?\}', '', e.tag)
    else:
        tag = e.tag
    return tag in s


def process(fn):
    global strip_element
    global options

    # ugly hack for testing: allow "-" for "/dev/stdin"
    if fn == "-":
        fn = "/dev/stdin"

    try:
        tree = ET.parse(fn)
    except BaseException:
        print("Error parsing %s" % fn, file=sys.stderr)
        raise

    root = tree.getroot()

    ########## space normalization and stripping ##########

    reduce_space(root, strip_element)

    ########## additional space ##########

    # convert tree into text and standoffs
    text, standoffs = text_and_standoffs(root)

    # traverse standoffs and mark each position before which a space
    # or a newline should be assured. Values are (pos, early), where
    # pos is the offset where the break should be placed, and early
    # determines whether to select the first or the last among
    # multiple alternative tags before/after which to place the break.
    respace = {}
    for so in standoffs:
        e = so.element
        if element_in_set(e, newline_wrap_element):
            # "late" newline gets priority
            if not (so.start in respace and (respace[so.start][0] == "\n" and
                                             respace[so.start][1] == False)):
                respace[so.start] = ("\n", True)
            respace[so.end] = ("\n", False)
        elif element_in_set(e, space_wrap_element):
            # newlines and "late" get priority
            if not (so.start in respace and (respace[so.start][0] == "\n" or
                                             respace[so.start][1] == False)):
                respace[so.start] = (" ", True)
            if not (so.end in respace and respace[so.end][0] == "\n"):
                respace[so.end] = (" ", False)

    # next, filter respace to remove markers where the necessary space
    # is already present in the text.

    # to allow the filter to take into account linebreaks that will be
    # introduced as part of the processing, maintain rewritten
    # positions separately. (live updating of the text would be too
    # expensive computationally.) As the processing is left-to-right,
    # it's enough to use this for preceding positions and to mark
    # inserts as appearing "before" the place where space is required.
    rewritten = {}

    filtered = {}
    for pos in sorted(respace.keys()):
        if respace[pos][0] == " ":
            # unnecessary if initial, terminal, or preceded/followed
            # by a space
            if not (preceding_space(pos, text, rewritten) or
                    following_space(pos, text, rewritten)):
                filtered[pos] = respace[pos]
                rewritten[pos - 1] = " "
        else:
            assert respace[pos][0] == "\n", "INTERNAL ERROR"
            # unnecessary if there's either a preceding or following
            # newline connected by space
            if not (preceding_linebreak(pos, text, rewritten) or
                    following_linebreak(pos, text, rewritten)):
                filtered[pos] = respace[pos]
                rewritten[pos - 1] = "\n"
    respace = filtered

    # for reference, create a map from elements to their parents in the tree.
    parent_map = {}
    for parent in root.getiterator():
        for child in parent:
            parent_map[child] = parent

    # for reference, create a map from positions to standoffs ending
    # at each.
    # TODO: avoid indexing everything; this is only required for
    # standoffs ending at respace positions
    end_map = {}
    for so in standoffs:
        if so.end not in end_map:
            end_map[so.end] = []
        end_map[so.end].append(so)

    # traverse standoffs again, adding the new elements as needed.
    for so in standoffs:

        if so.start in respace and respace[so.start][1]:
            # Early space needed here. The current node can be assumed
            # to be the first to "discover" this, so it's appropriate
            # to add space before the current node.  We can further
            # assume the current node has a parent (adding space
            # before the root is meaningless), so we can add the space
            # node as the preceding child in the parent.

            e = so.element
            assert e in parent_map, "INTERNAL ERROR: add space before root?"
            p = parent_map[e]
            i = index_in_parent(e, p)

            rse = ET.Element(INSERTED_ELEMENT_TAG)
            rse.text = respace[so.start][0]
            p.insert(i, rse)

            # done, clear
            del respace[so.start]

        if so.end in respace and respace[so.end][1] == False:
            # Late space needed here. Add after the current node iff
            # it's the first of the nodes with the longest span ending
            # here (i.e. the outermost).
            maxlen = max([s.end - s.start for s in end_map[so.end]])
            if so.end - so.start != maxlen:
                continue
            longest = [s for s in end_map[so.end] if s.end - s.start == maxlen]
            if so != longest[0]:
                continue

            # OK to add.
            e = so.element
            assert e in parent_map, "INTERNAL ERROR: add space after root?"
            p = parent_map[e]
            i = index_in_parent(e, p)

            rse = ET.Element(INSERTED_ELEMENT_TAG)
            rse.text = respace[so.end][0]
            p.insert(i + 1, rse)
            # need to relocate tail
            rse.tail = e.tail
            e.tail = ""

            # done, clear
            del respace[so.end]

    assert len(respace) == 0, "INTERNAL ERROR: failed to insert %s" % str(respace)

    # re-process to clear out consequtive space potentially introduced
    # in previous processing.
    strip_elements(root)
    trim_tails(root)

    # all done, output

    if options.stdout:
        tree.write(sys.stdout, encoding=OUTPUT_ENCODING)
        return True

    if options is not None and options.directory is not None:
        output_dir = options.directory
    else:
        output_dir = ""

    output_fn = os.path.join(output_dir, os.path.basename(fn))

    # TODO: better checking of path identify to protect against
    # clobbering.
    if output_fn == fn and not options.overwrite:
        print('respace: skipping output for %s: file would overwrite input (consider -d and -o options)' % fn, file=sys.stderr)
    else:
        # OK to write output_fn
        try:
            with open(output_fn, 'w') as of:
                tree.write(of, encoding=OUTPUT_ENCODING)
        except IOError as ex:
            print('respace: failed write: %s' % ex, file=sys.stderr)

    return True


def argparser():
    import argparse
    ap = argparse.ArgumentParser(
        description='Revise whitespace content of a PMC NXML file for text extraction.')
    ap.add_argument(
        '-d',
        '--directory',
        default=None,
        metavar='DIR',
        help='output directory')
    ap.add_argument(
        '-o',
        '--overwrite',
        default=False,
        action='store_true',
        help='allow output to overwrite input files')
    ap.add_argument(
        '-s',
        '--stdout',
        default=False,
        action='store_true',
        help='output to stdout')
    ap.add_argument('file', nargs='+', help='input PubMed Central NXML file')
    return ap


def main(argv):
    global options

    options = argparser().parse_args(argv[1:])

    for fn in options.file:
        process(fn)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
