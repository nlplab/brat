#!/usr/bin/env perl

# Applies heuristic rules to repair sentence splitting errors.
# Developed for use as postprocessing for the GENIA sentence
# splitter on PubMed abstracts, with minor tweaks for 
# full-text documents.

# Draws in part on heuristics included in Yoshimasa Tsuruoka's
# medss.pl script. (Thanks!)

# (c) 2010 Sampo Pyysalo. No rights reserved, i.e. do whatever
# you like with this.

use warnings;
use strict;

my $s = join("", <>);


# breaks sometimes missing after "?", "safe" cases
$s =~ s/\b([a-z]+\?) ([A-Z][a-z]+)\b/$1\n$2/g;
# breaks sometimes missing after "." separated with extra space, "safe" cases
$s =~ s/\b([a-z]+ \.) ([A-Z][a-z]+)\b/$1\n$2/g;

# no breaks producing lines only containing sentence-ending punctuation
$s =~ s/\n([.!?]+)\n/ $1\n/g;

# no breaks inside parens/brackets. (To protect against cases where a
# pair of locally mismatched parentheses in different parts of a large
# document happen to match, limit size of intervening context. As this
# is not an issue in cases where there are no interveining brackets,
# allow an unlimited length match in those cases.)

# unlimited length for no intevening parens/brackets
while ($s =~ s/\[([^\[\]\(\)]*)\n([^\[\]\(\)]*)\]/\[$1 $2\]/) { }
while ($s =~ s/\(([^\[\]\(\)]*)\n([^\[\]\(\)]*)\)/\($1 $2\)/) { }
# standard mismatched with possible intervening
while ($s =~ s/\[([^\[\]]{0,250})\n([^\[\]]{0,250})\]/\[$1 $2\]/) { }
while ($s =~ s/\(([^\(\)]{0,250})\n([^\(\)]{0,250})\)/\($1 $2\)/) { }
# ... nesting to depth one
while ($s =~ s/\[((?:[^\[\]]|\[[^\[\]]*\]){0,250})\n((?:[^\[\]]|\[[^\[\]]*\]){0,250})\]/\[$1 $2\]/) { }
while ($s =~ s/\(((?:[^\(\)]|\([^\(\)]*\)){0,250})\n((?:[^\(\)]|\([^\(\)]*\)){0,250})\)/\($1 $2\)/) { }


# no break after periods followed by a non-uppercase "normal word"
# (i.e. token with only lowercase alpha and dashes, with a minimum
# length of initial lowercase alpha).
$s =~ s/\.\n([a-z]{3}[a-z-]{0,}[ \.\:\,])/. $1/g;


# no break before CC ...
$s =~ s/\n(and )/ $1/g;
$s =~ s/\n(or )/ $1/g;
$s =~ s/\n(but )/ $1/g;
$s =~ s/\n(nor )/ $1/g;
$s =~ s/\n(yet )/ $1/g;
# or IN. (this is nothing like a "complete" list...)
$s =~ s/\n(of )/ $1/g;
$s =~ s/\n(in )/ $1/g;
$s =~ s/\n(by )/ $1/g;
$s =~ s/\n(as )/ $1/g;
$s =~ s/\n(on )/ $1/g;
$s =~ s/\n(at )/ $1/g;
$s =~ s/\n(to )/ $1/g;
$s =~ s/\n(via )/ $1/g;
$s =~ s/\n(for )/ $1/g;
$s =~ s/\n(with )/ $1/g;
$s =~ s/\n(that )/ $1/g;
$s =~ s/\n(than )/ $1/g;
$s =~ s/\n(from )/ $1/g;
$s =~ s/\n(into )/ $1/g;
$s =~ s/\n(upon )/ $1/g;
$s =~ s/\n(after )/ $1/g;
$s =~ s/\n(while )/ $1/g;
$s =~ s/\n(during )/ $1/g;
$s =~ s/\n(within )/ $1/g;
$s =~ s/\n(through )/ $1/g;
$s =~ s/\n(between )/ $1/g;
$s =~ s/\n(whereas )/ $1/g;
$s =~ s/\n(whether )/ $1/g;

# no sentence breaks in the middle of specific abbreviations
$s =~ s/(\be\.)\n(g\.)/$1 $2/g;
$s =~ s/(\bi\.)\n(e\.)/$1 $2/g;
$s =~ s/(\bi\.)\n(v\.)/$1 $2/g;

# no sentence break after specific abbreviations
$s =~ s/(\be\. ?g\.)\n/$1 /g;
$s =~ s/(\bi\. ?e\.)\n/$1 /g;
$s =~ s/(\bi\. ?v\.)\n/$1 /g;
$s =~ s/(\bvs\.)\n/$1 /g;
$s =~ s/(\bcf\.)\n/$1 /g;
$s =~ s/(\bDr\.)\n/$1 /g;
$s =~ s/(\bMr\.)\n/$1 /g;
$s =~ s/(\bMs\.)\n/$1 /g;
$s =~ s/(\bMrs\.)\n/$1 /g;


# possible TODO: filter excessively long / short sentences

print $s;
