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

# -N specifies "fielded" output and is assumed by tools using this script
# -J specifies restriction to the given UMLS semantic types
# METAMAP_ARGS="-N -J anab,anst,bdsu,bdsy,blor,bpoc,bsoj,celc,cell,emst,ffas,tisu"
METAMAP_ARGS="-N"


$METAMAP_ROOT/public_mm/bin/metamap12 $METAMAP_ARGS $@
