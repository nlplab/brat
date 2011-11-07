#!/usr/bin/env perl

# Special-purpose script for converting the GREC standoff variant into
# a format recognized by brat.

# The GREC corpus (http://www.nactem.ac.uk/GREC/) is distributed in a
# standoff format that allows multi-valued arguments to be specified
# with a syntax shown in the following example:
#
#    E8	GRE:T20 Theme:T11,T12
#
# (see http://www.nactem.ac.uk/GREC/standoff.html for specification.)
# This is not compatible with the BioNLP shared task-flavored standoff
# used in brat. This script rewrites such annotations so that separate
# arguments are used:
#
#    E8	GRE:T20 Theme1:T11, Theme2:T12
#
# This script can be invoked as
#
#    convert-GREC.pl data/GREC/FILENAME.a2
#
# where FILENAME is one of the GREC corpus filenames. To conver the
# entire GREC corpus standoff data at once (in bash shell),
#
#     for f in data/GREC/*.a2; do convert-GREC.pl $f > tmp; mv tmp $f; done
#
# can be used.

use warnings;
use strict;

while(<>) {
    # pass through annotations other than event lines (starting with
    # "E") without modification
    unless(/^E/) {
	print;
	next;
    }

    # parse as event annotation
    /^(E\d+)\t(.*)$/ or die "Error parsing line: $_";
    my ($eid, $args) = ($1,$2);
    my @args = split(/ +/, $args);
    
    my @newargs;
    my %next_free_idx;
    foreach my $arg (@args) {
	$arg =~ /^(.*?):(.*)$/ or die "Error parsing argument $arg on line: $_";
	my ($role,$ids) = ($1,$2);
	my @ids = split(/,/, $ids);

	# pass through single-valued arguments without modification
	if (@ids == 1) {
	    push(@newargs, $arg);
	    next;
	}

	# affix number to role for each id, starting from 1
	if (!defined $next_free_idx{$role}) {
	    $next_free_idx{$role}=1;
	}

	foreach my $id (@ids) {
	    my $idx=$next_free_idx{$role}++;
	    push(@newargs, "$role$idx:$id");
	}
    }

    # recompose event and write out
    $args=join(" ", @newargs);
    print "$eid\t$args\n";
}
