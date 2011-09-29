#/bin/sh

# Watches the Python code for changes and restarts when necessary
#
# Uses inotifywait from inotify-tools:
#
#   https://github.com/rvoicilas/inotify-tools
#
# Author:   Pontus Stenetorp    <pontus stenetorp se>
# Version:  2011-09-29

# TODO: Hard-coded lighttpd and its config for now

while true;
do
    # Watch all server code for writes
    inotifywait -qq -e close_write -r *.cgi *.fcgi `find server -name '*.py'`
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
