#!/usr/bin/env python

# Basic support for extracting data from .obo ontology files.
# Adapted from readobo.py in sols.

# TODO: replace with a proper lib.

import sys
import re
from string import lowercase

options = None

def case_normalize_initial(s):
    # to avoid lowercasing first letter of e.g. abbrevs, require two
    # lowercase letters after initial capital.
    if re.match(r'^[A-Z][a-z]{2,}', s):
        # lowercase first letter
        return s[0].lower()+s[1:]
    else:
        return s

def case_normalize_all_words(s):
    return " ".join([case_normalize_initial(w) for w in s.split(" ")])

class Term:
    def __init__(self, tid, name, synonyms=None, defs=None, 
                 is_a=None, part_of=None):
        self.tid      = tid
        self.name     = name
        self.synonyms = synonyms if synonyms is not None else []
        self.defs     = defs     if defs     is not None else []
        self.is_a     = is_a     if is_a     is not None else []
        self.part_of  = part_of  if part_of  is not None else []

        self.parents  = []
        self.children = []

        # part_of "parents" and "children"
        self.objects    = []
        self.components = []

        self.cleanup()

    def obo_idspace(self):
        # returns the "id space" part of the ID identifying the ontology.
        if ":" in self.tid:
            # standard format: sequence prior to first colon.
            # Special case: if all lowercased, uppercase in order to get
            # e.g. "sao" match the OBO foundry convention.
            s = self.tid[:self.tid.index(":")]
            if len([c for c in s if c in lowercase]) == len(s):
                return s.upper()
            else:
                return s
        else:
            # nonstandard, try to guess
            m = re.match(r'^(.[A-Za-z_]+)', self.tid)
            #print >> sys.stderr, "Warning: returning %s for id space of nonstandard ID %s" % (m.group(1), self.tid)
            return m.group(1)

    def resolve_references(self, term_by_id, term_by_name=None):
        # is_a
        for ptid, pname in self.is_a:
            if ptid not in term_by_id:
                print >> sys.stderr, "Warning: is_a term '%s' not found, ignoring" % ptid
                continue
            parent = term_by_id[ptid]
            # name is not required information; check if included
            # and mapping defined (may be undef for dup names)
            if pname is not None and term_by_name is not None and term_by_name[pname] is not None:
                assert parent == term_by_name[pname]
            if self in parent.children:
                print >> sys.stderr, "Warning: dup is-a parent %s for %s, ignoring" % (ptid, str(self))
            else:
                self.parents.append(parent)
                parent.children.append(self)

        # part_of
        for prel, ptid, pname in self.part_of:
            if ptid not in term_by_id:
                print >> sys.stderr, "Error: part_of term '%s' not found, ignoring" % ptid
                continue
            pobject = term_by_id[ptid]
            # same as above for name
            if pname is not None and term_by_name is not None and term_by_name[pname] is not None:
                assert pobject == term_by_name[pname]
            if self in pobject.components:
                print >> sys.stderr, "Warning: dup part-of parent %s for %s, ignoring" % (ptid, str(self))
            else:
                self.objects.append((prel, pobject))
                pobject.components.append((prel, self))

    def _case_normalize(self, cn_func):
        self.name = cn_func(self.name)
        for i in range(len(self.synonyms)):
            self.synonyms[i] = (cn_func(self.synonyms[i][0]), self.synonyms[i][1])
        for i in range(len(self.is_a)):
            if self.is_a[i][1] is not None:
                self.is_a[i] = (self.is_a[i][0], cn_func(self.is_a[i][1]))

    def case_normalize_initial(self):
        # case-normalize initial character
        global case_normalize_initial
        self._case_normalize(case_normalize_initial)

    def case_normalize_all_words(self):
        # case-normalize initial characters of all words
        global case_normalize_all_words
        self._case_normalize(case_normalize_all_words)

    def cleanup(self):
        # some OBO ontologies have extra "." at the end of synonyms
        for i, s in enumerate(self.synonyms):
            if s[-1] == ".":
                # only remove period if preceded by "normal word"
                if re.search(r'\b[a-z]{2,}\.$', s):
                    c = s[:-1]
                    print >> sys.stderr, "Note: cleanup: '%s' -> '%s'" % (s, c)
                    self.synonyms[i] = c

    def __str__(self):
        return "%s (%s)" % (self.name, self.tid)

def parse_obo(f, limit_prefixes=None, include_nameless=False):
    all_terms = []
    term_by_id = {}

    # first non-space block is ontology info
    skip_block = True
    tid, prefix, name, synonyms, definitions, is_a, part_of, obsolete = None, None, None, [], [], [], [], False
    for ln, l in enumerate(f):
        # don't attempt a full parse, simply match the fields we require
        if l.strip() == "[Term]":
            assert tid is None
            assert name is None
            assert is_a == []
            skip_block = False
        if l.strip() == "[Typedef]":
            skip_block = True
        elif re.match(r'^id:.*', l) and not skip_block:
            assert tid is None, str(ln)+' '+tid
            # remove comments, if any
            l = re.sub(r'\s*\!.*', '', l)

            # Note: do loose ID matching to allow nonstandard cases
            # such as "CS01" and similar in EHDAA2 ... actually, do
            # allow pretty much any ID since there's stuff like
            # UBERON:FMA_7196-MA_0000141-MIAA_0000085-XAO_0000328-ZFA_0000436
            # out there.
            #m = re.match(r'^id: (([A-Z]{2,}[a-z0-9_]*):\d+)\s*$', l)
            m = re.match(r'^id: (([A-Za-z](?:\S*(?=:)|[A-Za-z_]*)):?\S+)\s*$', l)
            if m is None:
                print >> sys.stderr, "line %d: failed to match id, ignoring: %s" % (ln, l.rstrip())
                tid, prefix, name, synonyms, is_a, part_of, obsolete = None, None, None, [], [], [], False
                skip_block = True
            else:
                tid, prefix = m.groups()
        elif re.match(r'^name:.*', l) and not skip_block:
            assert tid is not None
            assert name is None
            m = re.match(r'^name: (.*?)\s*$', l)
            assert m is not None
            name = m.group(1)
        elif re.match(r'^is_a:.*', l) and not skip_block:
            assert tid is not None
            #assert name is not None
            # the comment (string after "!") is not required.
            # curlies allowed for UBERON, which has stuff like
            # "is_a: UBERON:0000161 {source="FMA"} ! orifice"
            # multiple comments allowed for UBERON and VAO
            m = re.match(r'^is_a: (\S+) *(?:\{[^{}]*\} *)?(?:\!.*?)?\! *(.*?)\s*$', l)
            if m:
                is_a.append(m.groups())
            else:
                m = re.match(r'^is_a: (\S+)\s*$', l)
                if m is not None:
                    is_a.append((m.group(1), None))
                else:
                    print >> sys.stderr, "Error: failed to parse '%s'; ignoring is_a" % l
        elif re.match(r'^relationship:\s*\S*part_of', l) and not skip_block:
            assert tid is not None
            assert name is not None
            # strip 'OBO_REL:' if present (used at least in HAO, TAO
            # and VAO). Comment not required, but use to check if present.
            m = re.match(r'^relationship: +(?:OBO_REL:)?(\S+) +(\S+) *(?:\{[^{}]*\} *)?\! *(.*?)\s*$', l)
            if m:
                part_of.append(m.groups())
            else:
                m = re.match(r'^relationship: +(?:OBO_REL:)?(\S+) +(\S+)\s*$', l)
                if m is not None:
                    part_of.append((m.group(1), m.group(2), None))
                else:
                    print >> sys.stderr, "Error: failed to parse '%s'; ignoring part_of" % l
        elif re.match(r'^synonym:.*', l) and not skip_block:
            assert tid is not None
            assert name is not None
            # more permissive, there's strange stuff out there
            #m = re.match(r'^synonym: "([^"]*)" ([A-Za-z_ ]*?) *\[.*\]\s*$', l)
            m = re.match(r'^synonym: "(.*)" ([A-Za-z_ ]*?) *\[.*\]\s*$', l)
            assert m is not None, "Error: failed to parse '%s'" % l
            synstr, syntype = m.groups()
            if synstr == "":
                print >> sys.stderr, "Note: ignoring empty synonym on line %d: %s" % (ln, l.strip())
            else:
                synonyms.append((synstr,syntype))
        elif re.match(r'^def:.*', l) and not skip_block:
            assert tid is not None
            assert name is not None
            m = re.match(r'^def: "(.*)" *\[.*\]\s*$', l)
            assert m is not None, "Error: failed to parse '%s'" % l
            definition = m.group(1)
            if definition == "":
                print >> sys.stderr, "Note: ignoring empty def on line %d: %s" % (ln, l.strip())
            else:
                definitions.append(definition)
        elif re.match(r'^is_obsolete:', l):
            m = re.match(r'^is_obsolete:\s*true', l)
            if m:
                obsolete = True
        elif re.match(r'^\s*$', l):
            # if everything's blank, there's just a sequence of blanks;
            # skip.
            if (tid is None and prefix is None and name is None and
                synonyms == [] and definitions == [] and 
                is_a == [] and part_of == []):
                #print >> sys.stderr, "Note: extra blank line %d" % ln
                continue

            # field end
            if (obsolete or
                (limit_prefixes is not None and prefix not in limit_prefixes)):
                #print >> sys.stderr, "Note: skip %s : %s" % (tid, name)
                tid, prefix, name, synonyms, definitions, is_a, part_of, obsolete = None, None, None, [], [], [], [], False
            elif not skip_block:
                assert tid is not None, "line %d: no ID for '%s'!" % (ln, name)
                if name is None and not include_nameless:
                    print >> sys.stderr, "Note: ignoring term without name (%s) on line %d" % (tid, ln)
                else:
                    if tid not in term_by_id:
                        t = Term(tid, name, synonyms, definitions, 
                                 is_a, part_of)
                        all_terms.append(t)
                        term_by_id[tid] = t
                    else:
                        print >> sys.stderr, "Error: duplicate ID '%s'; discarding all but first definition" % tid
                tid, prefix, name, synonyms, definitions, is_a, part_of, obsolete = None, None, None, [], [], [], [], False
            else:
                pass
        else:
            # just silently skip everything else
            pass

    assert tid is None
    assert name is None
    assert is_a == []
    
    return all_terms, term_by_id

def argparser():
    import argparse

    ap=argparse.ArgumentParser(description="Extract terms from OBO ontology.")
    ap.add_argument("-l", "--limit", default=None, metavar="PREFIX", help="Limit processing to given ontology prefix or prefixes (multiple separated by \"|\").")
    ap.add_argument("-d", "--depth", default=None, metavar="INT", help="Limit extraction to given depth from initial nodes.")
    ap.add_argument("-nc", "--no-case-normalization", default=False, action="store_true", help="Skip heuristic case normalization of ontology terms.")
    ap.add_argument("-nm", "--no-multiple-inheritance", default=False, action="store_true", help="Exclude subtrees involving multiple inheritance.")
    ap.add_argument("-ns", "--no-synonyms", default=False, action="store_true", help="Do not extract synonyms.")
    ap.add_argument("-nd", "--no-definitions", default=False, action="store_true", help="Do not extract definitions.")
    ap.add_argument("-e", "--exclude", default=[], metavar="TERM", nargs="+", help="Exclude subtrees rooted at given TERMs.")
    ap.add_argument("-s", "--separate-children", default=[], default=False, action="store_true", help="Separate subontologies found as children of the given term.")
    ap.add_argument("file", metavar="OBO-FILE", help="Source ontology.")
    ap.add_argument("-p", "--separate-parents", default=[], default=False, action="store_true", help="Separate subontologies of parents of the given terms.")
    ap.add_argument("terms", default=[], metavar="TERM", nargs="*", help="Root terms from which to extract.")
    return ap

multiple_parent_skip_count = 0

def get_subtree_terms(root, collection=None, depth=0):
    global options
    global multiple_parent_skip_count

    if collection is None:
        collection = []

    if root.traversed or root.excluded:
        return False

    if options.depth is not None and depth > options.depth:
        return False

    if options.no_multiple_inheritance and len(root.parents) > 1:
        # don't make too much noise about this
        if multiple_parent_skip_count < 10:
            print >> sys.stderr, "Note: not traversing subtree at %s %s: %d parents" % (root.tid, root.name, len(root.parents))
        elif multiple_parent_skip_count == 10:
            print >> sys.stderr, "(further 'not traversing subtree; multiple parents' notes suppressed)"
        multiple_parent_skip_count += 1
        return False

    root.traversed = True

#     collection.append([root.name, root.tid, "name"])
    collection.append(root)
#     if not options.no_synonyms:
#         for synstr, syntype in root.synonyms:
#             collection.append([synstr, root.tid, "synonym "+syntype])
    for child in root.children:
        get_subtree_terms(child, collection, depth+1)
    return collection

def exclude_subtree(root):
    if root.traversed:
        return False
    root.traversed = True
    root.excluded = True
    for child in root.children:
        exclude_subtree(child)

def main(argv=None):
    global options

    arg = argparser().parse_args(argv[1:])
    options = arg

    if arg.depth is not None:
        arg.depth = int(arg.depth)
        assert arg.depth > 0, "Depth limit cannot be less than or equal to zero"

    limit_prefix = arg.limit
    if limit_prefix is None:
        limit_prefixes = None
    else:
        limit_prefixes = limit_prefix.split("|")

    fn = arg.file

    if not arg.no_case_normalization:
        for i in range(len(arg.terms)):
            # we'll have to guess here
            arg.terms[i] = case_normalize_initial(arg.terms[i])

    f = open(fn)
    all_terms, term_by_id = parse_obo(f, limit_prefixes)
    # resolve references, e.g. the is_a ID list into parent and child
    # object references
    for t in all_terms:
        t.resolve_references(term_by_id)

    if not arg.no_case_normalization:
        for t in all_terms:
            # FMA systematically capitalizes initial letter; WBbt has
            # a mix of capitalization conventions; SAO capitalizes all
            # words.
            if t.obo_idspace() in ("FMA", "WBbt"):
                t.case_normalize_initial()
            elif t.obo_idspace() == "SAO":
                t.case_normalize_all_words()

    print >> sys.stderr, "OK, parsed %d (non-obsolete) terms." % len(all_terms)

    term_by_name = {}
    for t in all_terms:
        if t.name not in term_by_name:
            term_by_name[t.name] = t
        else:
            print >> sys.stderr, "Warning: duplicate name '%s'; no name->ID mapping possible" % t.name
            # mark unavailable by name
            term_by_name[t.name] = None

    for rootterm in arg.terms:
        # we'll allow this for the "separate parents" setting        
        assert arg.separate_parents or rootterm in term_by_name, "Error: given term '%s' not found (or obsolete) in ontology!" % rootterm

    # mark children and parents
    for t in all_terms:
        t.children = []
        t.parents  = []
    for t in all_terms:
        for ptid, pname in t.is_a:
            if ptid not in term_by_id:
                print >> sys.stderr, "Error: is_a term '%s' not found, removing" % ptid
                continue
            parent = term_by_id[ptid]
            # name is not required information; check if included
            # and mapping defined (may be undef for dup names)
            if pname is not None and pname in term_by_name and term_by_name[pname] is not None:
                if parent != term_by_name[pname]:
                    print >> sys.stderr, "Warning: given parent name '%s' mismatches parent term name (via ID) '%s'" % (parent.name, pname)
            if t in parent.children:
                print >> sys.stderr, "Warning: ignoring dup parent %s for %s" % (ptid, str(t))
            else:
                t.parents.append(parent)
                parent.children.append(t)

    for t in all_terms:
        t.traversed = False
        t.excluded  = False

    for excludeterm in arg.exclude:
        assert excludeterm in term_by_name, "Error: exclude term '%s' not found (or obsolete) in ontology!" % excludeterm
        exclude_subtree(term_by_name[excludeterm])
        
    for t in all_terms:
        t.traversed = False

    rootterms = []
    if not arg.separate_parents:
        # normal processing
        for t in arg.terms:
            if t not in term_by_name:
                print >> sys.stderr, "Error: given term '%s' not found!" % t
                return 1
            else:
                rootterms.append(term_by_name[t])

        # if no terms are given, just extract from all roots.
        if len(rootterms) == 0:
            for t in all_terms:
                if len(t.parents) == 0:
                    rootterms.append(t)
            #print >> sys.stderr, "Extracting from %d root terms (%s)" % (len(rootterms), ", ".join(rootterms))
            print >> sys.stderr, "Extracting from %d root terms." % len(rootterms)

    else:
        assert not arg.separate_children, "Incompatible arguments"
        # identify new rootterms as the unique set of parents of the given terms. 
        # to simplify call structure for extraction from multiple ontologies.
        unique_parents = {}
        for t in arg.terms:
            # allow missing
            if t in term_by_name:
                for p in term_by_name[t].parents:
                    unique_parents[p] = True
        assert len(unique_parents) != 0, "Failed to find any of given terms"

        # mark the parents as excluded to avoid redundant traversal
        for p in unique_parents:
            p.excluded = True

        # set rootterms and use the existing "separate children"
        # mechanism to trigger traversal
        rootterms = [p for p in unique_parents]
        # make the extraction order stable for better diffs
        rootterms.sort(lambda a,b: cmp(a.name,b.name))
        arg.separate_children = True

        # debugging
        print >> sys.stderr, "Splitting at the following:", ",".join(rootterms)

    for rootterm in rootterms:
        if not arg.separate_children:
            # normal, just print out everything from the root term as one
            # block
#             for n, tid, ntype in get_subtree_terms(rootterm):
#                 print "%s\t%s\t%s" % (n, tid, ntype)
            for t in get_subtree_terms(rootterm):
                strs = []
                strs.append("name:Name:"+t.name)
                if not arg.no_synonyms:
                    for synstr, syntype in t.synonyms:
                        # never mind synonym type
                        #strs.append("name:synonym-"+syntype+':'+synstr)
                        strs.append("name:Synonym:"+synstr)
                if not arg.no_definitions:
                    for d in t.defs:
                        strs.append("info:Definition:"+d)
                # don't include ontology prefix in ID
                id_ = t.tid.replace(t.obo_idspace()+':', '', 1) 
                print id_ + '\t' + '\t'.join(strs)
#                 print "%s\t%s\t%s" % (n, tid, ntype)
        else:
            # separate the children of the root term in output
            for c in rootterm.children:
                stt = []
                get_subtree_terms(c, stt)
            for n, tid, ntype in stt:
                    print "%s\t%s\t%s\t%s" % (c.name, n, tid, ntype)

if __name__ == "__main__":
    sys.exit(main(sys.argv))
