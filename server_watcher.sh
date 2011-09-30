#/bin/sh

# Watches the Python code for changes and restarts when necessary
#
# Uses inotifywait from inotify-tools:
#
#   https://github.com/rvoicilas/inotify-tools
#
#   sudo apt-get install inotify-tools
#
# Author:   Pontus Stenetorp    <pontus stenetorp se>
# Version:  2011-09-29

# TODO: Hard-coded lighttpd and its config for now

while true;
do
    # Watch all server code for writes
    find . -iregex '.*\.\(py\|cgi\|fcgi\)' \
        | inotifywait -qq -e close_write --fromfile -
    echo `date`': Code change detected!'

    # Kill the existing server if any
    echo -n `date`': Killing old server... '
    ps aux | grep lighttpd_fcgi.conf | grep -v grep \
        | cut -d ' ' -f 4 | xargs -r kill
    echo 'Done!'

    # Start the server
    echo -n `date`': Starting server... '
    lighttpd -f lighttpd_fcgi.conf
    echo 'Done!'
done
