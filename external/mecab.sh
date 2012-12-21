#!/bin/sh

# MeCab Configuration and installation script
#
# Author:       Pontus Stenetorp    <pontus stenetorp se>
# Version:      2011-05-16

SCRIPT_RELDIR=`dirname $0`
SCRIPT_DIR=`cd $SCRIPT_RELDIR && pwd`

MECAB_VERSION=0.98
MECAB_IPADIC_VERSION=2.7.0-20070801
MECAB_LOCAL_DIR=${SCRIPT_DIR}/mecab/local
MECAB_DIR=${SCRIPT_DIR}/mecab-${MECAB_VERSION}
MECAB_IPADIC_DIR=${SCRIPT_DIR}/mecab-ipadic-${MECAB_IPADIC_VERSION}
MECAB_PYTHON_DIR=${SCRIPT_DIR}/mecab-python-${MECAB_VERSION}

# Extract the resources
( cd ${SCRIPT_DIR} && find . -name 'mecab-*.tar.gz' | xargs -n 1 tar xfz )

# Create the installation dir
mkdir -p ${MECAB_LOCAL_DIR}

# Build MeCab
( cd ${MECAB_DIR} && ./configure --prefix=${MECAB_LOCAL_DIR} \
    --enable-utf8-only && make install clean )

# Construct IPA dictionaries
( cd ${MECAB_IPADIC_DIR} && env PATH="${PATH}:${MECAB_LOCAL_DIR}/bin" \
    ./configure --prefix=${MECAB_LOCAL_DIR} --with-charset=utf8 \
    && make install clean )

# Build Python bindings
( cd ${MECAB_PYTHON_DIR} && env PATH="${PATH}:${MECAB_LOCAL_DIR}/bin" \
    python setup.py build_ext --inplace --rpath ${MECAB_LOCAL_DIR}/lib )
