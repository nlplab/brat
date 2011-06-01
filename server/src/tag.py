#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Tagging functionality.

Author:     Pontus Stenetorp
Version:    2011-04-
'''

from message import Messager

# XXX: Just ripped out of the old ajax server

# XXX TODO: replace this quick ugly hack with an invocation through
# the interface we designed for taggers
def tag_file(directory, document):
    import os
    textfn      = os.path.join(DATA_DIR, directory, document+'.txt')
    tagger_root = os.path.join(BASE_DIR, '../nlpwrap')
    tagger_cmd  = os.path.join(tagger_root, 'tag-NERsuite.sh')+" "+textfn
    try:
        os.system(tagger_cmd)
    except Exception, e:
        Messager.error("Failed to run tagger. Please contact the administrator(s).", duration=-1)
        from sys import stderr
        print >> stderr, e
        return
    taggedfn    = os.path.join(tagger_root, 'output', document+'.ner')

    # read in tagged, mark everything with AnnotationUnconfirmed
    import re
    try:
        f = open(taggedfn)
        outputlines = []
        next_comment_id = 1
        for l in f:
            m = re.match(r'^(T\d+)\t(\S+) (\d+) (\d+)\t(.*)', l)
            assert m, "Failed to parse tagger output line '%s'" % l
            tid, ttype, start, end, ttext = m.groups()
            # worse hack in bad hack: rename type
            if ttype == "Protein":
                ttype = "Gene_or_gene_product"
            l = "%s\t%s %s %s\t%s\n" % (tid, ttype, start, end, ttext)
            outputlines.append(l)
            outputlines.append('#%d\tAnnotationUnconfirmed %s\tAutomatically generated annotation, please confirm by clicking\n' % (next_comment_id, tid))
            next_comment_id += 1
        f.close()
    except Exception, e:
        Messager.error("Failed to read tagger output. Please contact the administrator(s).", duration=-1)
        from sys import stderr
        print >> stderr, e
        return

    # XXX TODO: incorporate via Annotation object
    # first-attempt hack: clobber the existing .ann
    try:
        annfn = os.path.join(DATA_DIR, directory, document+'.ann')
        f = open(annfn, 'wt')
        for l in outputlines:
            f.write(l)
        f.close()
    except Exception, e:
        Messager.error("Failed to store tagger output. Please contact the administrator(s).", duration=-1)
        from sys import stderr
        print >> stderr, e
        return
