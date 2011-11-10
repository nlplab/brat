#!/bin/sh

# Convert a True Type Font (TTF) to a Scalable Vector Graphics (SVG) font.
#
# Largely borrowed from:
#
#   https://github.com/zoltan-dulac/css3FontConverter
#
# For Ubuntu, install the script dependencies:
#
#   sudo apt-get install fontforge libbatik-java
#
# Author:   Pontus Stenetorp    <pontus stenetorp se>
# Version:  2011-11-10

# Copyright (c) 2011, Pontus Stenetorp <pontus stenetorp se>
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

### Constants
BATIK_TTF2SVG_FNAME=batik-ttf2svg.jar
# Using locate is a bit slow, but bound to work since we can't rely using
#   PATH for Batik
BATIK_TTF2SVG_PATH=`locate ${BATIK_TTF2SVG_FNAME}`
FONTFORGE_BIN=fontforge

### Dependency checking
if [ ! -f "${BATIK_TTF2SVG_PATH}" ]
then
    echo "ERROR: unable to locate ${BATIK_TTF2SVG_FNAME}" 1>&2
    exit 1
fi

`hash ${FONTFORGE_BIN} 2>&-`
if [ "$?" -ne "0" ]
then
    echo "ERROR: unable to locate ${FONTFORGE_BIN}" 1>&2
    exit 1
fi

for TTF_PATH in $*
do
    # Check if this looks like a TTF font
    `file ${TTF_PATH} | grep 'TrueType' > /dev/null`
    if [ "$?" -ne "0" ]
    then
        echo "ERROR: ${TTF_PATH} does not appear to be a TTF font"
        exit 1
    fi

    # ID creation is along the lines of Google web fonts
    # NOTE: This may require some tweaking to get in line with our CSS
    FONT_ID=`basename ${TTF_PATH} | sed -e 's|\.[^.]\+$||g' \
        -e 's/-\(Normal\|Regular\|Web\)//g' \
        -e 's|-| |g' -e 's|_| |g'`

    # Convert the font
    TMP_FILE=`tempfile`
    java -jar ${BATIK_TTF2SVG_PATH} ${TTF_PATH} -l 32 -h 127 \
        -o ${TMP_FILE} -id "${FONT_ID}"
    # Remove the kerning, browsers don't do it anyway and it saves space
    cat ${TMP_FILE} | grep -v '^<hkern' | grep -v -e '^<?xml' -e '^</\?defs' \
        -e '^</\?svg' > `echo ${TTF_PATH} | sed -e 's|\.ttf$|.svg|g'`
    rm -f ${TMP_FILE}
done
