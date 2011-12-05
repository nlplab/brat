#!/bin/sh

# Redact all affiliations from the repo for reviewing purposes.
#
# USAGE:
#
#   tools/anonymise.sh
#
# NOTE: IMPORTANT! The data in this file will not be redacted, so delete it
#   after you have run a redaction of all data. Also, don't be an idiot and
#   forget to erase the `.git` directory since obviously a reviewer can look
#   at the git history.
#
# Author:   Pontus Stenetorp    <pontus stenetorp se>
# Version:  2011-12-05

for TO_REDACT in \
    'Goran Topic' 'Goran Topić' 'Goran' 'amadanmath' \
        'goran is s u-tokyo ac jp' 'amadan mad scientist com' \
    'Pontus Stenetorp' 'Pontus' 'ninjin' 'pontus stenetorp se' \
        'pontus is s u-tokyo ac jp' \
    'Sampo Pyysalo' 'Sampo' 'smp is s u-tokyo ac jp' \
    'Illes Solt' 'Illes' 'solt tmit bme hu' 'illes solt gmail com' \
    'David McClosky' 'David' 'david.mcclosky gmail com'
do
    find . -type f -a -not -name anonymise.sh -print0 \
        | grep -v './.git/' \
        | xargs -r -0 grep -l "${TO_REDACT}" \
        | xargs -r sed -i -e "s|${TO_REDACT}|REDACTED|g"
done

echo 'It might be a good idea to check for links to:' 2>&1
echo '* Tsujii lab' 2>&1
echo '* GitHub' 2>&1
echo 2>&1
echo 'IMPORTANT!!! Remember to remove `.git` and this script!'
