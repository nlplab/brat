#!/bin/sh

# Convert SVG;s to PNG;s using Inkscape.
#
# Usage:
#
#   ./svg2png.sh [svg_path] ...
#
# Depends on Inkscape:
#
#   sudo apt-get install inkscape
#
# Back-ports of Inkscape stable to older Ubuntu versions:
#
#   https://launchpad.net/~inkscape.dev/+archive/stable
#
# Note: For "older" versions of Ubuntu it appears that some dependency for
#   Inkscape causes it to render SVG;s poorly (text/offset mismatches)
#
# Author:   Pontus Stenetorp <pontus stenetorp se>
# Version:  2011-11-16

INKSCAPE_BIN=inkscape

`hash ${INKSCAPE_BIN} 2>&-`
if [ "$?" -ne "0" ]
then
    echo "ERROR: unable to locate inkscape binary (tried '${INKSCAPE_BIN}')" \
        1>&2
    exit 1
fi

for SVG_PATH in $*
do
    PNG_PATH=`echo ${SVG_PATH} | sed -e 's|\.svg$|.png|g'`
    # Re-calculate the boundaries for the SVG, it won't be perfect but better
    ${INKSCAPE_BIN} --export-area-drawing --without-gui \
        --file=${SVG_PATH} --export-png=${PNG_PATH}
done
