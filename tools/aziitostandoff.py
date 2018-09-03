#!/usr/bin/env python

import re
import sys

try:
    import cElementTree as ET
except BaseException:
    import xml.etree.cElementTree as ET

# tags of elements to exclude from standoff output
EXCLUDED_TAGS = [
    "SURNAME",
    "AUTHOR",
    "REFERENCE",
    "AUTHORLIST",
    "JOURNAL",
    "YEAR",
    "P",
    "TITLE",
    "DIV",
    "HEADER",
    "FIGURE",
    "XREF",
    "CURRENT_SURNAME",
    "CURRENT_AUTHOR",
    "FOOTNOTE",
    "DATE",
    "TABLE",
    "CURRENT_NAME",
    "EQN",
    "EQ-S",
    "ISSUE",
    "REFERENCELIST",
    "PAPER",
    "METADATA",
    "FILENO",
    "FIGURELIST",
    "CURRENT_TITLE",
    "CURRENT_AUTHORLIST",
    "BODY",
    "ABSTRACT",
    "FOOTNOTELIST",
    "TABLELIST",
    "ACKNOWLEDGMENTS",
    "REF",
]
EXCLUDED_TAG = {t: True for t in EXCLUDED_TAGS}

# string to use to indicate elided text in output
ELIDED_TEXT_STRING = "[[[...]]]"

# maximum length of text strings printed without elision
MAXIMUM_TEXT_DISPLAY_LENGTH = 1000

# c-style string escaping for just newline, tab and backslash.
# (s.encode('string_escape') does too much for utf-8)


def c_escape(s):
    return s.replace('\\', '\\\\').replace('\t', '\\t').replace('\n', '\\n')


def strip_ns(tag):
    # remove namespace spec from tag, if any
    return tag if tag[0] != '{' else re.sub(r'\{.*?\}', '', tag)


class Standoff:
    def __init__(self, sid, element, start, end, text):
        self.sid = sid
        self.element = element
        self.start = start
        self.end = end
        self.text = text

    def strip(self):
        while self.start < self.end and self.text[0].isspace():
            self.start += 1
            self.text = self.text[1:]
        while self.start < self.end and self.text[-1].isspace():
            self.end -= 1
            self.text = self.text[:-1]

    def compress_text(self, l):
        if len(self.text) >= l:
            el = len(ELIDED_TEXT_STRING)
            sl = (l - el) / 2
            self.text = (
                self.text[:sl] + ELIDED_TEXT_STRING + self.text[-(l - sl - el):])

    def tag(self):
        return strip_ns(self.element.tag)

    def attrib(self):
        # remove namespace specs from attribute names, if any
        attrib = {}
        for a in self.element.attrib:
            if a[0] == "{":
                an = re.sub(r'\{.*?\}', '', a)
            else:
                an = a
            attrib[an] = self.element.attrib[a]
        return attrib

    def __str__(self):
        return "X%d\t%s %d %d\t%s\t%s" % \
            (self.sid, self.tag(), self.start, self.end,
             c_escape(self.text.encode("utf-8")),
             " ".join(['%s="%s"' % (k.encode("utf-8"), v.encode("utf-8"))
                       for k, v in list(self.attrib().items())]))


def txt(s):
    return s if s is not None else ""


next_free_so_id = 1


def text_and_standoffs(e, curroff=0, standoffs=None):
    global next_free_so_id

    if standoffs is None:
        standoffs = []
    startoff = curroff
    # to keep standoffs in element occurrence order, append
    # a placeholder before recursing
    so = Standoff(next_free_so_id, e, 0, 0, "")
    next_free_so_id += 1
    standoffs.append(so)
    setext, dummy = subelem_text_and_standoffs(
        e, curroff + len(txt(e.text)), standoffs)
    text = txt(e.text) + setext
    curroff += len(text)
    so.start = startoff
    so.end = curroff
    so.text = text
    return (text, standoffs)


def subelem_text_and_standoffs(e, curroff, standoffs):
    startoff = curroff
    text = ""
    for s in e:
        stext, dummy = text_and_standoffs(s, curroff, standoffs)
        text += stext
        text += txt(s.tail)
        curroff = startoff + len(text)
    return (text, standoffs)


NORM_SPACE_REGEX = re.compile(r'\s+')


def normalize_space(e, tags=None):
    if tags is None or strip_ns(e.tag) in tags:
        if e.text is not None:
            n = NORM_SPACE_REGEX.sub(' ', e.text)
            e.text = n
        if e.tail is not None:
            n = NORM_SPACE_REGEX.sub(' ', e.tail)
            e.tail = n
        if strip_ns(e.tag) in ('S', 'A-S'):
            e.tail = e.tail + '\n' if e.tail else '\n'

    for c in e:
        normalize_space(c)


def generate_id(prefix):
    if prefix not in generate_id._next:
        generate_id._next[prefix] = 1
    id_ = prefix + str(generate_id._next[prefix])
    generate_id._next[prefix] += 1
    return id_


generate_id._next = {}


def convert_s(s):
    sostrings = []

    tid = generate_id('T')
    type_ = s.attrib()['AZ'] if 'AZ' in s.attrib() else 'UNDEF'
    sostrings.append('%s\t%s %d %d\t%s' %
                     (tid, type_, s.start, s.end, s.text.encode("utf-8")))
    return sostrings


convert_function = {
    "S": convert_s,
    "A-S": convert_s,
}


def main(argv=[]):
    if len(argv) != 4:
        print("Usage:", argv[0], "IN-XML OUT-TEXT OUT-SO", file=sys.stderr)
        return -1

    in_fn, out_txt_fn, out_so_fn = argv[1:]

    # "-" for STDIN / STDOUT
    if in_fn == "-":
        in_fn = "/dev/stdin"
    if out_txt_fn == "-":
        out_txt_fn = "/dev/stdout"
    if out_so_fn == "-":
        out_so_fn = "/dev/stdout"

    tree = ET.parse(in_fn)
    root = tree.getroot()

    # normalize space in target elements
    normalize_space(root, ['S', 'A-S'])

    text, standoffs = text_and_standoffs(root)

    # eliminate extra space
    for s in standoffs:
        s.strip()

    # filter
    standoffs = [s for s in standoffs if not s.tag() in EXCLUDED_TAG]

    # convert selected elements
    converted = []
    for s in standoffs:
        if s.tag() in convert_function:
            converted.extend(convert_function[s.tag()](s))
        else:
            converted.append(s)
    standoffs = converted

    for so in standoffs:
        try:
            so.compress_text(MAXIMUM_TEXT_DISPLAY_LENGTH)
        except AttributeError:
            pass

    # open output files
    out_txt = open(out_txt_fn, "wt")
    out_so = open(out_so_fn, "wt")

    out_txt.write(text.encode("utf-8"))
    for so in standoffs:
        print(so, file=out_so)

    out_txt.close()
    out_so.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
