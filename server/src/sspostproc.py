#!/usr/bin/env python

# Python version of geniass-postproc.pl. Originally developed as a
# heuristic postprocessor for the geniass sentence splitter, drawing
# in part on Yoshimasa Tsuruoka's medss.pl.

from __future__ import with_statement

import re

INPUT_ENCODING = "UTF-8"
OUTPUT_ENCODING = "UTF-8"
DEBUG_SS_POSTPROCESSING = False

__initial = []

# TODO: some cases that heuristics could be improved on
# - no split inside matched quotes
# - "quoted." New sentence
# - 1 mg .\nkg(-1) .

# breaks sometimes missing after "?", "safe" cases
__initial.append((re.compile(r'\b([a-z]+\?) ([A-Z][a-z]+)\b'), r'\1\n\2'))
# breaks sometimes missing after "." separated with extra space, "safe" cases
__initial.append((re.compile(r'\b([a-z]+ \.) ([A-Z][a-z]+)\b'), r'\1\n\2'))

# join breaks creating lines that only contain sentence-ending punctuation
__initial.append((re.compile(r'\n([.!?]+)\n'), r' \1\n'))

# no breaks inside parens/brackets. (To protect against cases where a
# pair of locally mismatched parentheses in different parts of a large
# document happen to match, limit size of intervening context. As this
# is not an issue in cases where there are no interveining brackets,
# allow an unlimited length match in those cases.)

__repeated = []

# unlimited length for no intevening parens/brackets
__repeated.append((re.compile(r'(\([^\[\]\(\)]*)\n([^\[\]\(\)]*\))'),r'\1 \2'))
__repeated.append((re.compile(r'(\[[^\[\]\(\)]*)\n([^\[\]\(\)]*\])'),r'\1 \2'))
# standard mismatched with possible intervening
__repeated.append((re.compile(r'(\([^\(\)]{0,250})\n([^\(\)]{0,250}\))'), r'\1 \2'))
__repeated.append((re.compile(r'(\[[^\[\]]{0,250})\n([^\[\]]{0,250}\])'), r'\1 \2'))
# nesting to depth one
__repeated.append((re.compile(r'(\((?:[^\(\)]|\([^\(\)]*\)){0,250})\n((?:[^\(\)]|\([^\(\)]*\)){0,250}\))'), r'\1 \2'))
__repeated.append((re.compile(r'(\[(?:[^\[\]]|\[[^\[\]]*\]){0,250})\n((?:[^\[\]]|\[[^\[\]]*\]){0,250}\])'), r'\1 \2'))

__final = []

# no break after periods followed by a non-uppercase "normal word"
# (i.e. token with only lowercase alpha and dashes, with a minimum
# length of initial lowercase alpha).
__final.append((re.compile(r'\.\n([a-z]{3}[a-z-]{0,}[ \.\:\,\;])'), r'. \1'))

# no break in likely species names with abbreviated genus (e.g.
# "S. cerevisiae"). Differs from above in being more liberal about
# separation from following text.
__final.append((re.compile(r'\b([A-Z]\.)\n([a-z]{3,})\b'), r'\1 \2'))

# no break in likely person names with abbreviated middle name
# (e.g. "Anton P. Chekhov", "A. P. Chekhov"). Note: Won't do
# "A. Chekhov" as it yields too many false positives.
__final.append((re.compile(r'\b((?:[A-Z]\.|[A-Z][a-z]{3,}) [A-Z]\.)\n([A-Z][a-z]{3,})\b'), r'\1 \2'))

# no break before CC ..
__final.append((re.compile(r'\n((?:and|or|but|nor|yet) )'), r' \1'))

# or IN. (this is nothing like a "complete" list...)
__final.append((re.compile(r'\n((?:of|in|by|as|on|at|to|via|for|with|that|than|from|into|upon|after|while|during|within|through|between|whereas|whether) )'), r' \1'))

# no sentence breaks in the middle of specific abbreviations
__final.append((re.compile(r'\b(e\.)\n(g\.)'), r'\1 \2'))
__final.append((re.compile(r'\b(i\.)\n(e\.)'), r'\1 \2'))
__final.append((re.compile(r'\b(i\.)\n(v\.)'), r'\1 \2'))

# no sentence break after specific abbreviations
__final.append((re.compile(r'\b(e\. ?g\.|i\. ?e\.|i\. ?v\.|vs\.|cf\.|Dr\.|Mr\.|Ms\.|Mrs\.)\n'), r'\1 '))

# or others taking a number after the abbrev
__final.append((re.compile(r'\b([Aa]pprox\.|[Nn]o\.|[Ff]igs?\.)\n(\d+)'), r'\1 \2'))

# no break before comma (e.g. Smith, A., Black, B., ...)
__final.append((re.compile(r'(\.\s*)\n(\s*,)'), r'\1 \2'))

def refine_split(s):
    """
    Given a string with sentence splits as newlines, attempts to
    heuristically improve the splitting. Heuristics tuned for geniass
    sentence splitting errors.
    """

    if DEBUG_SS_POSTPROCESSING:
        orig = s

    for r, t in __initial:
        s = r.sub(t, s)

    for r, t in __repeated:
        while True:
            n = r.sub(t, s)
            if n == s: break
            s = n

    for r, t in __final:
        s = r.sub(t, s)

    # Only do final comparison in debug mode.
    if DEBUG_SS_POSTPROCESSING:
        # revised must match original when differences in space<->newline
        # substitutions are ignored
        r1 = orig.replace('\n', ' ')
        r2 = s.replace('\n', ' ')
        if r1 != r2:
            print >> sys.stderr, "refine_split(): error: text mismatch (returning original):\nORIG: '%s'\nNEW:  '%s'" % (orig, s)
            s = orig

    return s

if __name__ == "__main__":
    import sys
    import codecs

    # for testing, read stdin if no args
    if len(sys.argv) == 1:
        sys.argv.append('/dev/stdin')

    for fn in sys.argv[1:]:
        try:
            with codecs.open(fn, encoding=INPUT_ENCODING) as f:
                s = "".join(f.read())
                sys.stdout.write(refine_split(s).encode(OUTPUT_ENCODING))
        except Exception, e:
            print >> sys.stderr, "Failed to read", fn, ":", e
            
