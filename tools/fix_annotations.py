#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

# Preamble {{{
from __future__ import with_statement
from diff_match_patch import diff_match_patch  # NEEDS `pip install diff_match_patch_python`
from shutil import copy
import re

try:
    import annotation
except ImportError:
    import os.path
    from sys import path as sys_path
    # Guessing that we might be in the brat tools/ directory ...
    sys_path.append(os.path.join(os.path.dirname(__file__), '../server/src'))
    import annotation

# this seems to be necessary for annotations to find its config
sys_path.append(os.path.join(os.path.dirname(__file__), '..'))
# }}}



# Processing {{{
def start_tag(entity):
    attrlist = [entity.type]
    for attribute in entity.attributes:
        value = attribute.value
        if isinstance(value, bool):
            value = str(value).lower()
        attrlist.append(u'%s="%s"' % (attribute.type, cgi.escape(value)))
    return u'<%s>' % ' '.join(attrlist)

def end_tag(entity):
    return u'</%s>' % entity.type

def convert_files(docname, root, txtname, out):
    ann = annotation.TextAnnotations(docname)
    with open(txtname) as r:
        txt = r.read().decode('utf8')
    entities = list(ann.get_entities())
    for entity in entities:
        entity.attributes = []
    attributes = list(ann.get_attributes())
    entity_dict = {entity.id: entity for entity in entities}
    for attribute in attributes:
        try:
            entity = entity_dict[attribute.target]
            entity.attributes.append(attribute)
        except KeyError:
            # ignore event attributes
            pass
    startlist = [(entity.spans[0][0], -entity.spans[0][1], False, index, start_tag(entity)) for index, entity in enumerate(entities)]
    endlist = [(entity.spans[0][1], -entity.spans[0][0], True, -index, end_tag(entity)) for index, entity in enumerate(entities)]
    lastpos = len(txt)
    xml = ""
    for pos, _, _, _, tag in sorted(startlist + endlist, reverse=True):
        xml = tag + cgi.escape(txt[pos:lastpos]) + xml
        lastpos = pos
    xml = u'<%s>%s</%s>\n' % (root, cgi.escape(txt[0:lastpos]) + xml, root)
    out.write(xml.encode('utf8'))


def correct_annotations(orig_fn, ann_fn, change_fn):
    with annotation.TextAnnotations(ann_fn) as anns:
        orig_text = anns.get_document_text()
        with annotation.open_textfile(change_fn, 'r') as f:
            changed_text = f.read()
        diffs = diff_match_patch().diff_main(orig_text, changed_text)
        orig_offset = 0
        change_offset = 0
        offsets = []
        for diff in diffs:
            kind = diff[0]
            text = diff[1]
            size = len(text)
            if kind == 0:
                delta = 0
            elif kind == 1:
                delta = size
            elif kind == -1:
                delta = -size
            offsets.append((orig_offset, delta))
            if kind != 1:
                orig_offset += size
        offsets = offsets[::-1]        
        tbs = list(anns.get_textbounds())
        indices = []
        for tbi, tb in enumerate(tbs):
            for spani, span in enumerate(tb.spans):
                indices.append((span[0], tbi, spani, 0))
                indices.append((span[1], tbi, spani, 1))
        indices.sort(reverse=True)
        for orig_offset, delta in offsets:
            for index in indices:
                if index[0] < orig_offset: break
                frag = list(tbs[index[1]].spans[index[2]])
                frag[index[3]] += delta
                tbs[index[1]].spans[index[2]] = tuple(frag)
        for tb in tbs:
            if isinstance(tb, annotation.TextBoundAnnotationWithText):
                tb.text = annotation.DISCONT_SEP.join((changed_text[start:end] for start, end in tb.spans))
    copy(change_fn, orig_fn)
# }}}



# Parsing command line {{{
if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('original_text', help='The original TXT file (accompanied with ANN file)')
    parser.add_argument('changed_text', help='The changed TXT file')
    opts = parser.parse_args()

    opts.original_ann = re.sub(r'\.txt$', '', opts.original_text)

    correct_annotations(opts.original_text, opts.original_ann, opts.changed_text)
# }}}
