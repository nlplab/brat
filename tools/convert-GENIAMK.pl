#!/usr/bin/env perl

# Special-purpose script for converting a version of the GENIA
# Metaknowledge annotation from a standoff variant format into the
# brat standoff format.

use warnings;
use strict;

# textbound type mapping

my %typemap = (
    "Negative_Polarity" => "Polarity-Cue",
    "Positive_Polarity" => "Polarity-Cue",
    "Analysis_KT" => "KT-Cue",
    "Gen-Fact_KT" => "KT-Cue",
    "Gen-Method_KT" => "KT-Cue",
    "Investigation_KT" => "KT-Cue",
    "Observation_KT" => "KT-Cue",
    "L1_CL" => "CL-Cue",
    "L2_CL" => "CL-Cue",
    "L3_CL" => "CL-Cue",
    "High_Manner" => "Manner-Cue",
    "Neutral_Manner" => "Manner-Cue",
    "Low_Manner" => "Manner-Cue",
    "Current_Source" => "Source-Cue",
    "Other_Source" => "Source-Cue",
    );

# event role mapping
my %rolemap = (
    "theme" => "Theme",
    "cause" => "Cause",
    "Negative_Polarity" => "Cue",
    "Positive_Polarity" => "Cue",
    "Analysis_KT" => "Cue",
    "Gen-Fact_KT" => "Cue",
    "Gen-Method_KT" => "Cue",
    "Investigation_KT" => "Cue",
    "Observation_KT" => "Cue",
    "L1_CL" => "Cue",
    "L2_CL" => "Cue",
    "L3_CL" => "Cue",
    "High_Manner" => "Cue",
    "Neutral_Manner" => "Cue",
    "Low_Manner" => "Cue",
    "Current_Source" => "Cue",
    "Other_Source" => "Cue",
    );

for my $fn (@ARGV) {
    open(F, $fn) or die;
    my @l = <F>;
    close(F);

    # for ID revision, determine largest "T" ID in use in file
    my $maxt = 0;
    for (@l) {
	next unless (/^T(\d+)/);
	$maxt = $1 > $maxt ? $1 : $maxt;
    }

    # rewrite all "A" and "C" IDs (brat expects "T"), keep mapping
    my %idmap;
    my $tid = $maxt+1;
    for (@l) {
	# skip non-textbounds (fewer than 3 TAB-separated fields)	
	next if ((@_ = split(/\t/)) < 3);
	if (s/^([AC]\d+)/T$tid/) {
	    $idmap{$1}="T$tid";
	    $tid++;
	}
    }

    # remove duplicate textbounds, keep id mapping
    my @dedup;
    my %seen;
    for (@l) {
	unless (/^(T\S+)\t(.*)/) {
	    push(@dedup, $_);
	} else {
	    if (defined $seen{$2}) {
		$idmap{$1} = $seen{$2};
	    } else {
		push(@dedup, $_);
		$seen{$2} = $1;
	    }
	}
    }
    @l = @dedup;

    # shortcut transitive ID mappings (one step)
    for my $k (keys %idmap) {
	if (defined $idmap{$idmap{$k}}) {
	    $idmap{$k} = $idmap{$idmap{$k}};
	}
    }

    # rewrite references to remapped IDs
    for (@l) {
	# skip textbounds
	next if ((@_=split(/\t/)) >= 3);

	chomp;
	my @f = split(/\t/);
	if (/^E/) {
	    # event: 2nd TAB-separated field has ID refs in form ROLE:ID
	    my @newargs;
	    for my $arg (split(/ /, $f[1])) {
		die "Format error" unless ($arg =~ /^(.*):(.*)/);
		push(@newargs, $1.':'.(defined $idmap{$2} ? $idmap{$2} : $2));
	    }
	    $f[1] = join(' ', @newargs);
	} elsif (/^A/ && @f < 3) {
	    # attribute: 2nd TAB-separated field has ID ref as 2nd
	    # SPACE-separated value
	    my @v = split(/ /, $f[1]);
	    $v[1] = defined $idmap{$v[1]} ? $idmap{$v[1]} : $v[1];
	    $f[1] = join(' ', @v);
	}
	$_ = join("\t", @f)."\n";
    }
 
    # rewrite textbound annotation types
    for (@l) {
	next unless(/^(T\S+\t)(\S+)(.*\s?)$/);
	$_ = $1.(defined $typemap{$2} ? $typemap{$2} : $2).$3;
    }
    
    # rewrite event role types
    for (@l) {
	next unless(/^E/);

	my @f = split(/\t/);
	my @newargs;
	for my $arg (split(/ /, $f[1])) {
	    die "Format error" unless ($arg =~ /^(.*):(.*)/);
	    push(@newargs, (defined $rolemap{$1} ? $rolemap{$1} : $1).':'.$2);
	}
	$f[1] = join(' ', @newargs);	
	$_ = join("\t", @f)."\n";
    }
    
    # remove event arguments containing broken ID references
    my %knownid;
    for (@l) {
	$knownid{(@_=split(/\t/))[0]} = 1;
    }

    for (@l) {
	if (/^E/) {
	    chomp;
	    my @f = split(/\t/);
	    my @newargs;
	    for my $arg (split(/ /, $f[1])) {
		die "Format error" unless ($arg =~ /^(.*):(.*)/);
		if (defined $knownid{$2}) {
		    push(@newargs, $arg);
		} else {
		    print STDERR "Note: removing argument referencing undefined ID: $arg\n";
		}
	    }
	    $f[1] = join(' ', @newargs);
	    $_ = join("\t", @f)."\n";
	}
    }
    
    print @l;
}
