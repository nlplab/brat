#!/bin/bash

# Simple wrapper for a MetaMap pipeline.
# Expects input on STDIN, writes to STDOUT.

# NOTE: this script assumes MetaMap 2011 and requires that
# the MetaMap support services are running. If you have
# MetaMap installed in $MM, these can be started as
#
#    $MM/bin/skrmedpostctl start
#    $MM/bin/wsdserverctl start

METAMAP_ROOT=~/tools/MetaMap

# -N specifies "fielded" output and is assumed by tools using this
# script.
METAMAP_ARGS="-N"

$METAMAP_ROOT/public_mm/bin/metamap11 $METAMAP_ARGS $@
