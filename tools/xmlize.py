#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:


# Preamble {{{



try:
    import annotation
except ImportError:
    import os.path
    from sys import path as sys_path
    # Guessing that we might be in the brat tools/ directory ...
    sys_path.append(os.path.join(os.path.dirname(__file__), '../server/src'))
    import annotation

try:
    pass
except ImportError:
    import os.path
    from sys import path as sys_path
    # We are most likely on an old Python and need to use our internal version
    sys_path.append(os.path.join(os.path.dirname(__file__), '../server/lib'))

# this seems to be necessary for annotations to find its config
sys_path.append(os.path.join(os.path.dirname(__file__), '..'))

import re
# gathering the annotations into the XML {{{
import xml.etree.cElementTree as ET

# }}}



WORD_RE = re.compile(r'\S+')


def collect_sentences_and_get_words(sentences, ann, ssplitter):
    text = ann.get_document_text()
    words = []
    for sid, (sstart, send) in enumerate(ssplitter(text)):
        sentence = ET.SubElement(
            sentences,
            "sentence",
            start=str(sstart),
            end=str(send),
            id="s.%s" %
            sid)
        stext = text[sstart:send]
        for wid, m in enumerate(WORD_RE.finditer(stext)):
            wstart, wend, wtext = sstart + m.start(), sstart + m.end(), m.group()
            wid = "s.%s.w.%s" % (sid, wid)
            ET.SubElement(
                sentence,
                "word",
                start=str(wstart),
                end=str(wend),
                id=wid).text = wtext
            words.append((wstart, wend, wid, wtext))
    return words


def collect_annotations(annotations, ann, words):
    c = 1
    from collections import defaultdict
    cache = defaultdict(lambda: defaultdict(int))
    anns = {}
    suffixes = {}

    for a in ann.get_textbounds():
        aid = "ann%s" % c
        c += 1
        wids = " ".join(w[2] for w in words if any(
            span for span in a.spans if span[0] <= w[0] and w[1] <= span[1]))
        spans = " ".join("%s-%s" % span for span in a.spans)
        anns[a.id] = ET.SubElement(annotations,
                                   "annotation",
                                   id=aid,
                                   repr=a.get_text(),
                                   words=wids,
                                   spans=spans,
                                   type=a.type)

    for a in ann.get_events():
        tra = anns[a.trigger]
        cache[a.trigger][a.type] += 1
        suffix = cache[a.trigger][a.type]
        suffix = '' if suffix == 1 else str(suffix)
        suffixes[a.id] = (a.type, [(tra, suffix)])
        for arg in a.args:
            name = "%s%s.%s" % (a.type, suffix, arg[0])
            tra.set(name, anns[arg[1]].get('id'))

    for a in ann.get_equivs():
        for ent in a.entities:
            remaining = " ".join(anns[ent2].get('id')
                                 for ent2 in a.entities if ent2 != ent)
            anns[ent].set(a.type, remaining)

    for a in ann.get_relations():
        cache[a.arg1][a.type] += 1
        suffix1 = cache[a.arg1][a.type]
        suffix1 = '' if suffix1 == 1 else str(suffix1)
        name1 = "%s%s.%s" % (a.type, suffix1, a.arg2l)
        anns[a.arg1].set(name1, anns[a.arg2].get('id'))

        cache[a.arg2][a.type] += 1
        suffix2 = cache[a.arg2][a.type]
        suffix2 = '' if suffix2 == 1 else str(suffix2)
        name2 = "%s%s.%s" % (a.type, suffix2, a.arg1l)
        anns[a.arg2].set(name2, anns[a.arg1].get('id'))

        suffixes[a.id] = (
            a.type, [(anns[a.arg1], suffix1), (anns[a.arg2], suffix2)])

    norms = defaultdict(lambda: defaultdict(list))
    for a in ann.get_normalizations():
        norms[a.target][a.type].append("%s:%s" % (a.refdb, a.refid))
    for target, types in norms.items():
        for typ, refs in types.items():
            anns[target].set(typ, " ".join(refs))

    for a in ann.get_attributes():
        value = a.value
        if isinstance(value, bool):
            value = 'true' if value else 'false'

        if a.target in suffixes:
            typ, suffixlist = suffixes[a.target]
            for ta, suffix in suffix_list:
                name = "%s%s.%s" % (typ, suffix, a.type)
                ta.set(name, value)
        else:
            anns[a.target].set(a.type, value)


def convert(doc_bare, result, ssplitter):
    ann = annotation.TextAnnotations(doc_bare)
    document = ET.Element("document")
    sentences = ET.SubElement(document, "sentences")
    annotations = ET.SubElement(document, "annotations")

    words = collect_sentences_and_get_words(sentences, ann, ssplitter)
    collect_annotations(annotations, ann, words)

    tree = ET.ElementTree(document)
    tree.write(result)
# }}}


# handling file names {{{
def convert_all(docs, dest, nl):
    if nl:
        from ssplit import newline_sentence_boundary_gen as sentence_boundary_gen
    else:
        from ssplit import regex_sentence_boundary_gen as sentence_boundary_gen

    if dest:
        import os
        import os.path
        import errno
        try:
            os.makedirs(dest)
        except OSError as e:  # Python >2.5
            if e.errno == errno.EEXIST and os.path.isdir(dest):
                pass
            else:
                raise

    for doc in docs:
        doc_bare = name_without_extension(doc)

        if dest:
            basename = os.path.basename(doc)
            result = "%s.xml" % os.path.join(dest, basename)
        else:
            result = "%s.xml" % doc_bare

        convert(doc_bare, result, sentence_boundary_gen)
# }}}


# Utility {{{
KNOWN_FILE_SUFF = [annotation.TEXT_FILE_SUFFIX] + annotation.KNOWN_FILE_SUFF
EXTENSIONS_RE = '\\.(%s)$' % '|'.join(KNOWN_FILE_SUFF)


def name_without_extension(file_name):
    return re.sub(EXTENSIONS_RE, '', file_name)
# }}}


# Command-line invocation {{{
def argparser():
    import argparse

    ap = argparse.ArgumentParser(description="Produce an XML of a document")
    ap.add_argument(
        "docs",
        metavar="<doc>",
        nargs="+",
        help="Document to convert")
    ap.add_argument("dest", metavar="<dest>", nargs="?",
                    help="Destination directory (default: same)")
    ap.add_argument("-n", "--newline", action='store_true',
                    help="Newline splitting strategy (default: regex)")
    return ap


def main(argv=None):
    if argv is None:
        argv = sys.argv
    args = argparser().parse_args(argv[1:])

    convert_all(args.docs, args.dest, args.newline)


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
# }}}
