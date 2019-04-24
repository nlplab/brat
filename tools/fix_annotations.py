#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

# Preamble {{{

import re
from shutil import copy

# NEEDS `pip install diff_match_patch`
from diff_match_patch import diff_match_patch

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
def correct_annotations(orig_fn, ann_fn, change_fn):
    with annotation.TextAnnotations(ann_fn) as anns:
        orig_text = anns.get_document_text()
        with annotation.open_textfile(change_fn, 'r') as f:
            changed_text = f.read()
        diffs = diff_match_patch().diff_main(orig_text, changed_text)
        orig_offset = 0
        offsets = []
        for diff in diffs:
            kind = diff[0]
            text = diff[1]
            size = len(text)
            delta = size * kind
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
                if index[0] < orig_offset:
                    break
                frag = list(tbs[index[1]].spans[index[2]])
                frag[index[3]] += delta
                tbs[index[1]].spans[index[2]] = tuple(frag)
        for tb in tbs:
            if isinstance(tb, annotation.TextBoundAnnotationWithText):
                tb.text = annotation.DISCONT_SEP.join(
                    (changed_text[start:end] for start, end in tb.spans))
    copy(change_fn, orig_fn)
# }}}



# Parsing command line {{{
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Fit existing annotations to changed text using Google diff-match-patch")
    parser.add_argument(
        'original_text',
        help='The original TXT file (accompanied with ANN file)')
    parser.add_argument('changed_text', help='The changed TXT file')
    opts = parser.parse_args()

    opts.original_ann = re.sub(r'\.txt$', '', opts.original_text)

    correct_annotations(
        opts.original_text,
        opts.original_ann,
        opts.changed_text)
# }}}
