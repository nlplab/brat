#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

from __future__ import with_statement

'''
Split merged BioNLP Shared Task annotations into separate files.

Author:     Sampo Pyysalo
Version:    2011-02-24
'''

import sys
import re

try:
    import argparse
except ImportError:
    from os.path import basename
    from sys import path as sys_path
    # We are most likely on an old Python and need to use our internal version
    sys_path.append(join_path(basename(__file__), '../server/lib'))
    import argparse

# if True, performs extra checking to assure that the input and output
# contain the same data. This costs a bit of execution time.
DEBUG=True

class ArgumentError(Exception):
    def __init__(self, s):
        self.errstr = s

    def __str__(self):
        return 'Argument error: %s' % (self.errstr)

class SyntaxError(Exception):
    def __init__(self, line, errstr=None, line_num=None):
        self.line = line
        self.errstr = errstr
        self.line_num = str(line_num) if line_num is not None else "(undefined)"

    def __str__(self):
        return 'Syntax error on line %s ("%s")%s' % (self.line_num, self.line, ": "+self.errstr if self.errstr is not None else "")

class ProcessingError(Exception):
    pass

class Annotation(object):
    # Special value to use as the type for comment annotations.
    COMMENT_TYPE = "<COMMENT>"

    _typere = re.compile(r'^([a-zA-Z][a-zA-Z0-9_-]*)\b')

    @staticmethod
    def _parse_type(s):
        '''
        Attempts to parse the given line as a BioNLP ST - flavoured
        standoff annotation, returning its type.
        '''
        if not s or s[0].isspace():
            raise SyntaxError(s, "ID missing")
        if s[0].isalnum() or s[0] == '*':
            # Possible "standard" ID. Assume type can be found
            # in second TAB-separated field.
            fields = s.split("\t")
            if len(fields) < 2:
                raise SyntaxError(s, "No TAB in annotation")
            m = Annotation._typere.search(fields[1])
            if not m:
                raise SyntaxError(s, "Failed to parse type in \"%s\"" % fields[1])
            return m.group(1)
            
        elif s[0] == '#':
            # comment; any structure allowed. return special type
            return Annotation.COMMENT_TYPE
        else:
            raise SyntaxError(s, "Unrecognized ID")

    def __init__(self, s):
        self.ann_string = s
        self.type = Annotation._parse_type(s)

    def __str__(self):
        return self.ann_string

def argparser():
    ap=argparse.ArgumentParser(description="Split merged BioNLP ST annotations into separate files.")
    ap.add_argument("-a1", "--a1types", default="Protein", metavar="TYPE[,TYPE...]", help="Annotation types to place into .a1 file")
    ap.add_argument("-a2", "--a2types", default="[OTHER]", metavar="TYPE[,TYPE...]", help="Annotation types to place into .a2 file")
    ap.add_argument("-d", "--directory", default=None, metavar="DIR", help="Output directory")
    # TODO: don't clobber existing files
    #ap.add_argument("-f", "--force", default=False, action="store_true", help="Force generation even if output files exist")
    ap.add_argument("-s", "--skipempty", default=False, action="store_true", help="Skip output for empty split files")
    ap.add_argument("-i", "--idrewrite", default=False, action="store_true", help="Rewrite IDs following BioNLP ST conventions")
    ap.add_argument("files", nargs='+', help="Files in merged BioNLP ST-flavored standoff")
    return ap

def parse_annotations(annlines, fn="(unknown)"):
    annotations = []
    for ln, l in enumerate(annlines):
        if not l.strip():
            print >> sys.stderr, "Warning: ignoring empty line %d in %s" % (ln, fn)
            continue
        try:
            annotations.append(Annotation(l))
        except SyntaxError, e:
            raise SyntaxError(l, e.errstr, ln)
    return annotations

DEFAULT_TYPE = "<DEFAULT>"

def split_annotations(annotations, typemap):
    """
    Returns the given annotations split into N collections
    as specified by the given type mapping. Returns a dict
    of lists keyed by the type map keys, containing the
    annotations.
    """
    d = {}

    for a in annotations:
        if a.type in typemap:
            t = a.type
        elif DEFAULT_TYPE in typemap:
            t = DEFAULT_TYPE
        else:
            raise ArgumentError("Don't know where to place annotation of type '%s'" % a.type)
        s = typemap[t]

        if s not in d:
            d[s] = []
        d[s].append(a)
        
    return d

def type_mapping(arg):
    """
    Generates a mapping from types to filename suffixes
    based on the given arguments.
    """
    m = {}
    # just support .a1 and .a2 now
    for suff, typestr in (("a1", arg.a1types),
                          ("a2", arg.a2types)):
        for ts in typestr.split(","):
            # default arg
            t = ts if ts != "[OTHER]" else DEFAULT_TYPE
            if t in m:
                raise ArgumentError("Split for '%s' ambiguous (%s or %s); check arguments." % (ts, m[t], suff))
            m[t] = suff
    return m

def output_file_name(fn, directory, suff):
    import os.path

    dir, base = os.path.split(fn)
    root, ext = os.path.splitext(base)    

    if not directory:
        # default to directory of file
        directory = dir

    return os.path.join(directory, root+"."+suff)

def annotation_lines(annotations):
    return [str(a) for a in annotations]

def write_annotation_lines(fn, lines):
    with open(fn, 'wt') as f:
        for l in lines:
            f.write(l)

def read_annotation_lines(fn):
    with open(fn) as f:
        return f.readlines()

def verify_split(origlines, splitlines):
    orig = origlines[:]
    split = []
    for k in splitlines:
        split.extend(splitlines[k])

    orig.sort()
    split.sort()

    orig_only = []
    split_only = []
    oi, si = 0, 0
    while oi < len(orig) and si < len(split):
        if orig[oi] == split[si]:
            oi += 1
            si += 1
        elif orig[oi] < split[si]:
            orig_only.append(orig[oi])
            oi += 1
        else:
            assert split[si] < orig[si]
            split_only.append(split[si])
            si += 1
    while oi < len(orig):
        orig_only.append(orig[oi])
        oi += 1
    while si < len(split):
        split_only.append(split[si])
        si += 1

    difference_found = False
    for l in split_only:
        print >> sys.stderr, "Split error: split contains extra line '%s'" % l
        difference_found = True
    for l in orig_only:
        # allow blank lines to be removed
        if l.strip() == "":
            continue
        print >> sys.stderr, "Split error: split is missing line '%s'" % l
        difference_found = True

    if difference_found:
        raise ProcessingError

def process_file(fn, typemap, directory, mandatory):
    annlines = read_annotation_lines(fn)
    annotations = parse_annotations(annlines)

    splitann = split_annotations(annotations, typemap)

    # always write these, even if they will be empty
    for t in mandatory:
        splitann[t] = splitann.get(t, [])

    splitlines = {}
    for suff in splitann:
        splitlines[suff] = annotation_lines(splitann[suff])

    if DEBUG:
        verify_split(annlines, splitlines)

    for suff in splitann:
        ofn = output_file_name(fn, directory, suff)
        write_annotation_lines(ofn, splitlines[suff])

def main(argv=None):
    if argv is None:
        argv = sys.argv
    arg = argparser().parse_args(argv[1:])

    try:
        typemap = type_mapping(arg)
    except ArgumentError, e:
        print >> sys.stderr, e
        return 2

    if arg.skipempty: 
        mandatory_outputs = []
    else:
        mandatory_outputs = ["a1", "a2"]

    for fn in arg.files:
        try:
            process_file(fn, typemap, arg.directory, mandatory_outputs)
        except IOError, e:
            print >> sys.stderr, "Error: failed %s, skip processing (%s)" % (fn, e)            
        except SyntaxError, e:
            print >> sys.stderr, "Error: failed %s, skip processing (%s)" % (fn, e)            
        except:
            print >> sys.stderr, "Fatal: unexpected error processing %s" % fn
            raise

    return 0

if __name__ == "__main__":
    sys.exit(main())
