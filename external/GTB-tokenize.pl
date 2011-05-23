#!/usr/bin/perl

# Implements a GENIA Treebank - like tokenization.

# NOTE: intended differences:
# - Does not break "protein(s)" -> "protein ( s )"

use warnings;
use strict;

my %rerightbracket = ( "(" => "\\)", "[" => "\\]", "{" => "\\}" );
my $balancedbrackets;
$balancedbrackets = qr/([(\[{])([^()\[\]{}]+|(??{$balancedbrackets}))*(??{$rerightbracket{$1}})/;

# Supported options:
# -ptb  : PTB escapes
# -mccc : Special processing for McClosky-Charniak parser input
# -sp   : Special processing for Stanford parser+PTBEscapingProcessor input
#         (not necessary for Stanford Parser version 1.6.5 and newer)

my $ptb_escaping       = 0;
my $single_quotes_only = 0;
my $escape_token_internal_parens = 0;

while(@ARGV > 0 && $ARGV[0] =~ /^-./) {
    if($ARGV[0] eq "-ptb") {
	$ptb_escaping = 1;
    } elsif($ARGV[0] eq "-mccc") {
	$ptb_escaping = 1;
	# current version of McCC doesn't correctly tag closing
	# double quotes
	$single_quotes_only = 1;
    } elsif($ARGV[0] eq "-sp") {
	# current version of Stanford parser PTBEscapingProcessor
	# doesn't correctly escape word-internal parentheses
	$escape_token_internal_parens = 1;
    } else {
	die "Unrecognized argument: $ARGV[0]\n";
    }
    shift(@ARGV);
}

while(<>) {
    # Need starting and ending space for some of the following to work
    # properly at the beginnings and ends of strings.
    s/^/ /;
    s/$/ /;

    if($ptb_escaping) {
	if($single_quotes_only) {
	    # special case for McCC: escape into single quotes.
	    s/([ \(\[\{\<])\"/$1 ' /g;
	} else {
	    # standard PTB escaping
	    s/([ \(\[\{\<])\"/$1 `` /g;
	}
    } else {
	# no escaping
	s/([ \(\[\{\<])\"/$1 \" /g;
    }

    s/\.\.\./ ... /g;

    # To avoid breaking names of chemicals, complexes and similar,
    # only add space to special chars if there's already space on
    # at least one side.

    s/([,;:@#]) / $1 /g;
    s/ ([,;:@#])/ $1 /g;

    s/\$/ \$ /g;
    s/\%/ \% /g;
    s/\&/ \& /g;

    # separate punctuation followed by space even if there's closing
    # brackets or quotes in between, but only sentence-final for
    # periods (don't break e.g. "E. coli").
    s/([,:;])([\[\]\)\}\>\"\']* +)/ $1$2/g;
    s/(\.+)([\[\]\)\}\>\"\']* +)$/ $1$2/g;
    # and these always
    s/\?/ \? /g;
    s/\!/ \! /g;

    # separate greater than and less than signs, avoiding breaking
    # "arrows" (e.g. "-->", ">>") and compound operators (e.g. "</=")
    s/((?:=\/)?<+(?:\/=|--+>?)?)/ $1 /g;
    s/((?:<?--+|=\/)?>+(?:\/=)?)/ $1 /g;
    
    # break dashes, not breaking up "arrows"
    s/(<?--+\>?)/ $1 /g;

    # parens only separated when there's space around a balanced
    # bracketing. This aims to avoid splitting e.g. beta-(1,3)-glucan,
    # CD34(+), CD8(-)CD3(-)

    # recursive, slow
#     while(s/ ([(\[{])((?! )(?:[^()\[\]{}]*|(??{$balancedbrackets}))*)((??{$rerightbracket{$1}})) / $1 $2 $3 /) { }
#     while(s/ ([(\[{])((?:[^()\[\]{}]*|(??{$balancedbrackets}))*)(?<! )((??{$rerightbracket{$1}})) / $1 $2 $3 /) { }

    # non-recursive, comparatively fast but a bit of a hack

    # First "protect" token-internal brackets by replacing them with
    # their PTB escapes. "Token-internal" brackets are defined as
    # matching brackets of which at least one has no space on either
    # side. To match GTB tokenization for cases like "interleukin
    # (IL)-mediated", and "p65(RelA)/p50", treat following dashes and
    # slashes as space.  Nested brackets are resolved inside-out;
    # to get this right, add a heuristic considering boundary
    # brackets as "space".

    # Special case (rareish): "protect" cases with dashes after
    # paranthesized expressions that cannot be abbreviations to avoid
    # breaking up e.g. "(+)-pentazocine". Here, "cannot be
    # abbreviations" is taken as "contains no uppercase charater".
    s/\(([^ A-Z()\[\]{}]+)\)-/-LRB-${1}-RRB--/g;

    my $escaped;
    do {
	$escaped = 0;
	# "token-internal" defined as above
	$escaped++ if(s/(?<![ (\[{])\(([^ ()\[\]{}]*)\)/-LRB-${1}-RRB-/);
	$escaped++ if(s/\(([^ ()\[\]{}]*)\)(?![ )\]}\/-])/-LRB-${1}-RRB-/);
	$escaped++ if(s/(?<![ (\[{])\[([^ ()\[\]{}]*)\]/-LSB-${1}-RSB-/);
	$escaped++ if(s/\[([^ ()\[\]{}]*)\](?![ )\]}\/-])/-LSB-${1}-RSB-/);
	$escaped++ if(s/(?<![ (\[{])\{([^ ()\[\]{}]*)\}/-LCB-${1}-RCB-/);
	$escaped++ if(s/\{([^ ()\[\]{}]*)\}(?![ )\]}\/-])/-LCB-${1}-RCB-/);
	# variant defining "token-internal" as "no space on either
	# side of either bracket"
# 	$escaped++ if(s/(?<! )\(([^ ()\[\]{}]*)\)(?! )/-LRB-${1}-RRB-/);
# 	$escaped++ if(s/(?<! )\[([^ ()\[\]{}]*)\](?! )/-LSB-${1}-RSB-/);
# 	$escaped++ if(s/(?<! )\{([^ ()\[\]{}]*)\}(?! )/-LCB-${1}-RCB-/);
    } while($escaped);

    # Remaining brackets are not token-internal and should be
    # surrounded by space.
    s/\(/ -LRB- /g;
    s/\)/ -RRB- /g;
    s/\[/ -LSB- /g;
    s/\]/ -RSB- /g;
    s/\{/ -LCB- /g;
    s/\}/ -RCB- /g;

    if($ptb_escaping) {
	if($single_quotes_only) {
	    # special case for McCC: escape into single quotes.
	    s/\"/ ' /g;
	} else {
	    # standard PTB escaping
	    s/\"/ '' /g;
	}
    } else {
	# no escaping
	s/\"/ \" /g;
	    
    }
  
    s/ (\'+)/ $1 /g;
    # rough heuristic to avoid breaking up 3' and 5'
    s/(?<![35'])(\'+) / $1 /g;

    # This more frequently disagrees than agrees with GTB
#     # Separate slashes preceded by space (can arise from
#     # e.g. splitting "p65(RelA)/p50"
#     s/ \// \/ /g;

    s/\'s / \'s /g;
    s/\'S / \'S /g;
    s/\'m / \'m /g;
    s/\'M / \'M /g;
    s/\'d / \'d /g;
    s/\'D / \'D /g;
    s/\'ll / \'ll /g;
    s/\'re / \'re /g;
    s/\'ve / \'ve /g;
    s/n\'t / n\'t /g;
    s/\'LL / \'LL /g;
    s/\'RE / \'RE /g;
    s/\'VE / \'VE /g;
    s/N\'T / N\'T /g;
    
    s/ Cannot / Can not /g;
    s/ cannot / can not /g;
    s/ D\'ye / D\' ye /g;
    s/ d\'ye / d\' ye /g;
    s/ Gimme / Gim me /g;
    s/ gimme / gim me /g;
    s/ Gonna / Gon na /g;
    s/ gonna / gon na /g;
    s/ Gotta / Got ta /g;
    s/ gotta / got ta /g;
    s/ Lemme / Lem me /g;
    s/ lemme / lem me /g;
    s/ More\'n / More \'n /g;
    s/ more\'n / more \'n /g;
    s/\'Tis / \'T is /g;
    s/\'tis / \'t is /g;
    s/\'Twas / \'T was /g;
    s/\'twas / \'t was /g;
    s/ Wanna / Wan na /g;
    s/ wanna / wan na /g;

    if(!$ptb_escaping) {
	if(!$escape_token_internal_parens) {
	    s/-LRB-/\(/g;
	    s/-RRB-/\)/g;
	    s/-LSB-/\[/g;
	    s/-RSB-/\]/g;
	    s/-LCB-/\{/g;
	    s/-RCB-/\}/g;
	} else {
	    # only unescape if a space can be matched on both
	    # sides of the bracket. Note that this won't work
	    # for sentence-final brackets unless there's extra
	    # terminal space.
	    s/ -LRB- / \( /g;
	    s/ -RRB- / \) /g;
	    s/ -LSB- / \[ /g;
	    s/ -RSB- / \] /g;
	    s/ -LCB- / \{ /g;
	    s/ -RCB- / \} /g;
	}
    }
    
    # normalize space
    s/  +/ /g;
    s/^ +//;
    s/ +$//;

    print;
}
