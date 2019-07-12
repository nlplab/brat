#!/bin/sh

# Attempt to diagnose problems with the brat server that the server itself
# can't diagnose (since it might not even be alive in the first place, lacking
# CGI and so on).
#
# Example:
#
#    tools/troubleshooting.sh http://localhost/~brat/
#
# Author:   Pontus Stenetorp    <pontus stenetorp se>
# Version:  2012-05-22

if [ $# -ne 1 ]
then
    echo "Usage: ${0} url_to_brat_installation" 1>&2
    exit 1
fi
BRAT_URL=$1
SCRIPT_DIR=`dirname $0`

# Baby-steps, do we even have Python?
/usr/bin/env python3 -c 'print("Hello world!")' > /dev/null 2>&1
if [ $? != 0 ]
then
    echo 'You do not appear to have Python installed.' 2>&1
    echo 'Please install Python for the brat server to be able to run.' 2>&1
    exit 1
fi

# Run the Python component of this script, we opt for Python rather than curl
# since there is a sickness in the community now-a-days to strip away close to
# every single package that isn't needed to play minesweeper or edit a Word
# document (yes Ubuntu, that is the likes of you).
${SCRIPT_DIR}/troubleshooting.py ${BRAT_URL}
# Preserve the Python script exit code and exit
exit $?
