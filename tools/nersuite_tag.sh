#!/bin/bash

# Simple wrapper for an NERsuite pipeline using a fixed set of models.
# Expects input on STDIN, writes to STDOUT.

# Output format setting

OUTPUT_FORMAT=conll
# This didn't work out, NERsuite can't guarantee that offsets match
#OUTPUT_FORMAT=brat

# Model locations

GTAG_MODEL=~/local/models/models_gtagger/
NERS_MODEL=~/local/models/models_nersuite/all_merged.data.m

# Dictionaries

# NOTE: if you have a different number of dictionaries, you'll have to
# tweak the code below also (sorry)
DICT_DIR=~/local/models/dic/
DICT1=EntrezGene.8xpath.dic.cdbpp
DICT2=UMLS.all_class.dic.cdbpp

# NERsuite components; add path if you have a local installation

TOKENIZER=nersuite_tokenizer
GTAGGER=nersuite_gtagger
DTAGGER=nersuite_dic_tagger
NERSUITE=nersuite


# Run as a straight pipeline

$TOKENIZER $@ |
     $GTAGGER -d $GTAG_MODEL $@ |
     $DTAGGER $DICT_DIR/$DICT1 $@ |
     $DTAGGER $DICT_DIR/$DICT2 $@ |
     $NERSUITE tag -m $NERS_MODEL -o $OUTPUT_FORMAT $@
