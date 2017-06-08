#!/usr/bin/env python

# Given a set of brat-flavored standoff .ann files, catenates them
# into a single .ann file (with reference to the corresponding .txt
# files) so that the resulting .ann applies for the simple catenation
# of the .txt files.

from __future__ import with_statement

import sys
import re
import os
import codecs

def parse_id(l):
    m = re.match(r'^((\S)(\S*))', l)
    assert m, "Failed to parse ID: %s" % l
    return m.groups()

def parse_key_value(kv):
    m = re.match(r'^(\S+):(\S+)$', kv)
    assert m, "Failed to parse key-value pair: %s" % kv
    return m.groups()

def join_key_value(k, v):
    return "%s:%s" % (k, v)

def remap_key_values(kvs, idmap):
    remapped = []
    for kv in kvs:
        k, v = parse_key_value(kv)
        v = idmap.get(v, v)
        remapped.append(join_key_value(k, v))
    return remapped

def remap_relation_idrefs(l, idmap):
    fields = l.split('\t')
    assert len(fields) >= 2, "format error"

    type_args = fields[1].split(" ")
    assert len(type_args) >= 3, "format error"

    args = type_args[1:]
    args = remap_key_values(args, idmap)

    fields[1] = " ".join(type_args[:1]+args)
    return '\t'.join(fields)

def remap_event_idrefs(l, idmap):
    fields = l.split('\t')
    assert len(fields) >= 2, "format error"

    type_args = fields[1].split(" ")
    type_args = remap_key_values(type_args, idmap)

    fields[1] = " ".join(type_args)
    return '\t'.join(fields)

def remap_attrib_idrefs(l, idmap):
    fields = l.split('\t')
    assert len(fields) >= 2, "format error"

    type_args = fields[1].split(" ")
    assert len(type_args) >= 2, "format error"

    args = type_args[1:]
    args = [idmap.get(a,a) for a in args]

    fields[1] = " ".join(type_args[:1]+args)
    return '\t'.join(fields)

def remap_note_idrefs(l, idmap):
    # format matches attrib in relevant parts
    return remap_attrib_idrefs(l, idmap)

def remap_equiv_idrefs(l, idmap):
    fields = l.split('\t')
    assert len(fields) >= 2, "format error"

    type_args = fields[1].split(" ")
    assert len(type_args) >= 3, "format error"

    args = type_args[1:]
    args = [idmap.get(a,a) for a in args]

    fields[1] = " ".join(type_args[:1]+args)
    return '\t'.join(fields)

def main(argv):
    filenames = argv[1:]

    # read in the .ann files and the corresponding .txt files for each
    anns = []
    texts = []
    for fn in filenames:
        assert re.search(r'\.ann$', fn), 'Error: argument %s not a .ann file.' % fn
        txtfn = re.sub(r'\.ann$', '.txt', fn)

        with open(fn, 'r') as annf:
            anns.append(annf.readlines())

        with open(txtfn, 'r') as txtf:
            texts.append(txtf.read())

    # process each .ann in turn, keeping track of the "base" offset
    # from (conceptual) catenation of the texts.
    baseoff = 0
    for i in range(len(anns)):
        # first, revise textbound annotation offsets by the base
        for j in range(len(anns[i])):
            l = anns[i][j]
            # see http://brat.nlplab.org/standoff.html for format
            m = re.match(r'^(T\d+\t\S+) (\d+) (\d+)(.*\n?)', l)
            if not m:
                continue
            begin, startoff, endoff, end = m.groups()

            startoff = int(startoff) + baseoff
            endoff   = int(endoff) + baseoff
            anns[i][j] = "%s %d %d%s" % (begin, startoff, endoff, end)

        baseoff += len(texts[i])

    # determine the full set of IDs currently in use in any of the
    # .anns
    reserved_id = {}
    for i in range(len(anns)):
        for l in anns[i]:
            aid, idchar, idseq = parse_id(l)
            reserved_id[aid] = (idchar, idseq)

    # use that to determine the next free "sequential" ID for each
    # initial character in use in IDs.
    idchars = set([aid[0] for aid in reserved_id])
    next_free_seq = {}
    for c in idchars:
        maxseq = 1
        for aid in [a for a in reserved_id if a[0] == c]:
            idchar, idseq = reserved_id[aid]
            try:
                idseq = int(idseq)
                maxseq = max(idseq, maxseq)
            except ValueError:
                # non-int ID tail; harmless here
                pass
        next_free_seq[c] = maxseq + 1

    # next, remap IDs: process each .ann in turn, keeping track of
    # which IDs are in use, and assign the next free ID in case of
    # collisions from catenation. Also, remap ID references
    # accordingly.
    reserved = {}
    for i in range(len(anns)):
        idmap = {}
        for j in range(len(anns[i])):
            l = anns[i][j]
            aid, idchar, idseq = parse_id(l)

            # special case: '*' IDs don't need to be unique, leave as is
            if aid == '*':
                continue

            if aid not in reserved:
                reserved[aid] = True
            else:
                newid = "%s%d" % (idchar, next_free_seq[idchar])
                next_free_seq[idchar] += 1

                assert aid not in idmap
                idmap[aid] = newid

                l = "\t".join([newid]+l.split('\t')[1:])
                reserved[newid] = True

            anns[i][j] = l

        # id mapping complete, next remap ID references
        for j in range(len(anns[i])):
            l = anns[i][j].rstrip()
            tail = anns[i][j][len(l):]
            aid, idchar, idseq = parse_id(l)

            if idchar == "T":
                # textbound; can't refer to anything
                pass
            elif idchar == "R":
                # relation
                l = remap_relation_idrefs(l, idmap)
            elif idchar == "E":
                # event
                l = remap_event_idrefs(l, idmap)
            elif idchar == "M" or idchar == "A":
                # attribute
                l = remap_attrib_idrefs(l, idmap)
            elif idchar == "*":
                # equiv
                l = remap_equiv_idrefs(l, idmap)
            elif idchar == "#":
                # note
                l = remap_note_idrefs(l, idmap)
            else:
                # ???
                print >> sys.stderr, "Warning: unrecognized annotation, cannot remap ID references: %s" % l

            anns[i][j] = l+tail
                
    # output
    for i in range(len(anns)):
        for l in anns[i]:
            sys.stdout.write(l)

if __name__ == "__main__":
    sys.exit(main(sys.argv))
