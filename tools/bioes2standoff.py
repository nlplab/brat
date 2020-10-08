#!/usr/bin/env python3

try:
    from annotation import TextAnnotations, TextBoundAnnotationWithText
except ImportError:
    import os.path
    from sys import path as sys_path
    # Guessing that we might be in the brat tools/ directory ...
    sys_path.append(os.path.join(os.path.dirname(__file__), '../server/src'))
    from annotation import TextAnnotations, TextBoundAnnotationWithText

import csv
import sys
import re
import argparse


bio_re = re.compile("^(\S+) ([BIOES])(?:-(\S+))?$")

class Standoffizer:
    def __init__(self, text, subs, start=0):
        self.text = text
        self.subs = subs
        self.start = start

    def __iter__(self):
        offset = 0
        for sub in self.subs:
            pos = self.text.index(sub, offset)
            offset = pos + len(sub)
            yield (self.start + pos, self.start + offset)


def read_text(filename):
    with open(filename, "rt", encoding="utf-8") as r:
        return r.read()


def read_bio(filename):
    tokens = []
    with open(filename, "rt", encoding="utf-8") as r:
        for lineno, line in enumerate(r, 1):
            line = line.rstrip()
            match = bio_re.match(line)
            if not match:
                print("Syntax error in {}:{}".format(filename, lineno), file=sys.stderr)
                continue
            tokens.append(match.groups())
        return tokens


def get_standoffs(text, tokens):
    standoff_iter = Standoffizer(text, (token[0] for token in tokens))
    return [(*token, *standoff) for token, standoff in zip(tokens, standoff_iter)]


def make_annotation(doc, accu):
    spans = [(accu[0][3], accu[-1][4])]
    label = accu[0][2] or "Entity"
    TextBoundAnnotationWithText(spans, doc.get_new_id('T'), label, doc)


def get_doc(tokens, text):
    doc = TextAnnotations(text=text)
    accu = []
    for token in tokens:
        tag = token[1]
        if tag in "BSO" and accu:
            make_annotation(doc, accu)
            accu = []
        if tag in "BESI":
            accu.append(token)
        if tag in "ES":
            make_annotation(doc, accu)
            accu = []

    if accu:
        make_annotation(doc, accu)

    return doc


def convert(text, bio, output=None):
    text = read_text(text)
    tokens = read_bio(bio)
    tokens = get_standoffs(text, tokens)
    doc = get_doc(tokens, text)

    if output:
        with open(output, "wt", encoding="utf-8") as w:
            w.write(str(doc))
    else:
        sys.stdout.write(str(doc))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("text", help="text file")
    parser.add_argument("bio", help="bio file")
    parser.add_argument("output", nargs="?", help="output (ann) file")
    args = parser.parse_args()

    convert(args.text, args.bio, args.output)

if __name__ == "__main__":
    main()
