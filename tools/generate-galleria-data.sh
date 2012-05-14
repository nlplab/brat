#!/bin/bash

# Special-purpose script to generate a JavaScript-formatted dictionary
# containing data for the galleria image gallery for the brat front
# page.

# Assumes files to display are .png files contained in the directory
# frontpage-img/. Further, for each "FILENAME.png" file, acts on the
# following files (if present):
#
# - FILENAME.ignore: skips FILENAME.png in processing
# - FILENAME.txt: uses content as title (first line) and description (lines
#   other than the first) in the galleria data

IMGDIR='frontpage-img'

first=1
for f in $IMGDIR/*.png; do
    # skip if the .ignore file exists
    ignf=${f%.png}.ignore
    if [ -e "$ignf" ]; then
	continue
    fi

    # grab contents of .txt file if exists
    txtf=${f%.png}.txt
    if [ -e "$txtf" ]; then
	title=`head -n 1 $txtf`
	desc=`tail -n +2 $txtf | egrep -v '^[[:space:]]*$' | perl -pe 's/\n/<br\/>/g' | perl -pe 's/<br\/>$//'`
    else
	title=''
	desc=''
    fi

    # IE can't stand extra commas
    if [ $first -ne 1 ]; then
	echo ","
    fi
    first=0

    echo -n \
"{
    image: '$f',
    title: '$title',
    description: '$desc'
}"
done

echo