#!/usr/bin/env python3

"""Attempt to diagnose common problems with the brat server by using HTTP.

Author:     Pontus Stenetorp    <pontus stenetorp se>
Version:    2012-05-22
"""

from http.client import (FORBIDDEN, MOVED_PERMANENTLY, OK, TEMPORARY_REDIRECT,
                         HTTPConnection, HTTPSConnection)
from sys import stderr
from urllib.parse import urlparse

# Constants
CONNECTION_BY_SCHEME = {
    'http': HTTPConnection,
    'https': HTTPSConnection,
}
###

# Handle the horridness of Pythons httplib with redirects and moves


def _request_wrap(conn, method, url, body=None,
                  headers=None):
    depth = 0
    curr_conn = conn
    curr_url = url
    while depth < 100:  # 100 is a nice arbitary number
        curr_conn.request(method, curr_url, body,
                          headers=headers if headers is not None else {})
        res = curr_conn.getresponse()
        if res.status not in (MOVED_PERMANENTLY, TEMPORARY_REDIRECT, ):
            return res
        res.read()  # Empty the results
        res_headers = dict(res.getheaders())
        url_soup = urlparse(res_headers['Location'])
        # Note: Could give us a "weird" scheme, but fuck it... can't be arsed
        # to think of all the crap http can potentially throw at us
        try:
            curr_conn = CONNECTION_BY_SCHEME[url_soup.scheme](url_soup.netloc)
        except KeyError:
            assert False, 'redirected to unknown scheme, dying'
        curr_url = url_soup.path
        depth += 1
    assert False, 'redirects and moves lead us astray, dying'


def main(args):
    # Old-style argument handling for portability
    if len(args) != 2:
        print('Usage: %s url_to_brat_installation' % (args[0], ), file=stderr)
        return -1
    brat_url = args[1]
    url_soup = urlparse(brat_url)

    if url_soup.scheme:
        try:
            Connection = CONNECTION_BY_SCHEME[url_soup.scheme.split(':')[0]]
        except KeyError:
            print(('ERROR: Unknown url scheme %s, try http or '
                              'https') % url_soup.scheme, file=stderr)
            return -1
    else:
        # Not a well-formed url, we'll try to guess the user intention
        path_soup = url_soup.path.split('/')
        assumed_netloc = path_soup[0]
        assumed_path = '/' + '/'.join(path_soup[1:])
        print(('WARNING: No url scheme given, assuming scheme: '
                          '"http", netloc: "%s" and path: "%s"'
                          ) % (assumed_netloc, assumed_path, ), file=stderr)
        url_soup = url_soup._replace(scheme='http', netloc=assumed_netloc,
                                     path=assumed_path)
        Connection = HTTPConnection

    # Check if we can load the base url
    conn = Connection(url_soup.netloc)
    res = _request_wrap(conn, 'HEAD', url_soup.path)
    if res.status != OK:
        print(('Unable to load "%s", please check the url.'
                          ) % (brat_url, ), file=stderr)
        print(('Does the url you provdide point to your brat '
                          'installation?'), file=stderr)
        return -1
    res.read()  # Dump the data so that we can make another request

    # Do we have an ajax.cgi?
    ajax_cgi_path = url_soup.path + '/ajax.cgi'
    ajax_cgi_url = url_soup._replace(path=ajax_cgi_path).geturl()
    res = _request_wrap(conn, 'HEAD', ajax_cgi_path)
    if res.status == FORBIDDEN:
        print(('Received forbidden (403) when trying to access '
                          '"%s"') % (ajax_cgi_url, ), file=stderr)
        print('Have you perhaps forgotten to enable execution of CGI in '
              ' your web server configuration?')
        return -1
    elif res.status != OK:
        print(('Unable to load "%s", please check your url. Does '
                          'it point to your brat installation?') % (ajax_cgi_url, ), file=stderr)
        return -1
    # Verify that we actually got json data back
    res_headers = dict(res.getheaders())
    try:
        content_type = res_headers['Content-Type']
    except KeyError:
        content_type = None

    if content_type != 'application/json':
        print(('Didn\'t receive json data when accessing "%s"%s.'
                          ) % (ajax_cgi_url,
                               ', instead we received %s' % content_type
                               if content_type is not None else ''), file=stderr)
        print(('Have you perhaps forgotten to add a handler for '
                          'CGI in your web server configuration?'), file=stderr)
        return -1

    # Doctor says, this seems okay
    print('Congratulations! Your brat server appears to be ready to run.')
    print('However, there is the possibility that there are further errors, '
          'but at least the server should be capable of communicating '
          'these errors to the client.')
    return 0


if __name__ == '__main__':
    from sys import argv
    exit(main(argv))
