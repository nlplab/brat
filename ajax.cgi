#!/usr/bin/env python3
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

"""Entry for CGI calls to brat. A simple wrapper around the CGI handling that
then delegates the work to the CGI-agnostic brat server.

Author:     Pontus Stenetorp    <pontus is s u-tokyo ac jp>
Version:    2011-02-07
"""

# Standard library imports
from cgi import FieldStorage
from os import environ
from os.path import dirname
from os.path import join as path_join
from sys import path as sys_path, stdout

# Local imports
sys_path.append(path_join(dirname(__file__), 'server/src'))

from server import serve


stdout = open(stdout.fileno(), mode='w', encoding='utf8', buffering=1)

def main(args):
    # Get data required for server call
    try:
        remote_addr = environ['REMOTE_ADDR']
    except KeyError:
        remote_addr = None
    try:
        remote_host = environ['REMOTE_HOST']
    except KeyError:
        remote_host = None
    try:
        cookie_data = environ['HTTP_COOKIE']
    except KeyError:
        cookie_data = None

    params = FieldStorage()

    # Call main server
    cookie_hdrs, response_data = serve(params, remote_addr, remote_host,
                                       cookie_data)

    # Package and send response
    if cookie_hdrs is not None:
        response_hdrs = [hdr for hdr in cookie_hdrs]
    else:
        response_hdrs = []
    response_hdrs.extend(response_data[0])

    stdout.write('\n'.join('%s: %s' % (k, v) for k, v in response_hdrs))
    stdout.write('\n')
    stdout.write('\n')
    stdout.write(response_data[1])
    return 0


def profile_main(argv):
    # runs main() with profiling, storing in a rotating set of files
    # in work. To see a profile, run e.g.
    # python -c 'import pstats;
    # pstats.Stats("work/serverprofile0").strip_dirs().sort_stats("time").print_stats()'
    # | less
    import cProfile
    import os.path
    for i in range(0, 10):
        pfn = 'work/serverprofile' + str(i)
        if not os.path.exists(pfn):
            break
    if os.path.exists(pfn):
        # rotate back; TODO: clear next in rotation
        pfn = 'work/serverprofile0'
    cProfile.run('main(argv)', pfn)


if __name__ == '__main__':
    from sys import argv, exit
    exit(main(argv))
    # To turn on server profiles, comment out the line above and use the one below.
    # exit(profile_main(argv))
