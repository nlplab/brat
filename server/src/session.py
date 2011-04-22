#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

# TODO: Update the example usage
'''
Session handling class.

Usage example:

    from session import Session
    session = Session()
    print "Content-Type: text/plain\n"
    counter = session['counter'] = session.get('counter', 0) + 1
    if counter <= 5:
        print "Counter is %s" % counter
    else:
        print "Logged off."
        session.invalidate()
    session.close()

API:
    new Session(name, dir, path, max_age)
        Needs to be called before the response body starts!
        name:    cookie's name ["sid"]
        dir:     directory where sessions will be stored ["sessions"]
        path:    cookie's path restriction [None, i.e. whole site]
        domain:  cookie's domain restriction [None, i.e. this site]
        max_age: session validity, in seconds or timedelta [None, i.e. until browser closes]
                 (note that resolution is in minutes, so less than 60 usually makes no sense)

    session.close()
        Last thing to do in a script: save the session.
        No further modifications possible.

    session.invalidate()
        Delete the session.
        No further modifications possible.

    value = session[key]
    session[key] = value
    del session[key]
    value = session.get(key, default)
        The usual suspects.
        Default defaults to None.

    The session object will also be globally available as Session.instance.

Author:     Goran Topic         <goran is s u-tokyo ac jp>
Author:     Pontus Stenetorp    <pontus is s u-tokyo ac jp>
Version:    2011-03-11
'''

from Cookie import SimpleCookie, CookieError
from atexit import register as atexit_register
from datetime import datetime, timedelta
from os import environ
from os.path import join as path_join
# TODO: Full imports
import hashlib, shelve


# TODO: Pythonista overlook
class Session(object):
    def __init__(self, name='sid', dir='sessions', path=None, domain=None, max_age=None):

        self._name = name
        now = datetime.utcnow();

        # blank cookie
        self._cookie = SimpleCookie()

        if environ.has_key('HTTP_COOKIE'):
            # cookie already exists, see what's in it
            self._cookie.load(environ['HTTP_COOKIE'])

        try:
            # what's our session ID?
            self.sid = self._cookie[name].value;
        except KeyError:
            # there isn't any, make a new session ID
            remote = environ.get('REMOTE_ADDR')
            self.sid = hashlib.sha224('%s-%s' % (remote, now)).hexdigest()

        self._cookie.clear();
        self._cookie[name] = self.sid

        # set/reset path
        if path:
            self._cookie[name]['path'] = path
        else:
            self._cookie[name]['path'] = ''

        # set/reset domain
        if domain:
            self._cookie[name]['domain'] = domain
        else:
            self._cookie[name]['domain'] = ''

        # set/reset expiration date
        if max_age:
            if isinstance(max_age, int):
                max_age = timedelta(seconds=max_age)
            expires = now + max_age
            self._cookie[name]['expires'] = expires.strftime('%a, %d %b %Y %H:%M:%S')
        else:
            self._cookie[name]['expires'] = ''

        # to protect against cookie-stealing JS, make our cookie
        # available only to the browser, and not to any scripts
        try:
            # This will not work for Python 2.5 and older
            self._cookie[name]['httponly'] = True
        except CookieError:
            pass

        # persist the session data
        self._shelf_file = path_join(dir, self.sid)
        # -1 signifies the highest available protocol version
        self._shelf = shelve.open(self._shelf_file, protocol=-1, writeback=True)

    def print_cookie(self):
        # send the headers
        print "Cache-Control: no-store, no-cache, must-revalidate"
        print self._cookie

    def close(self):
        # save the data
        self._shelf.close()

    def invalidate(self):
        from os import unlink

        # remove and expire the session
        self._shelf.close()
        unlink(self._shelf_file)
        self._cookie[self._name]['expires'] = 0

    def __getitem__(self, key):
        return self._shelf[key]

    def __setitem__(self, key, value):
        self._shelf[key] = value

    def __delitem__(self, key):
        del self._shelf[key]

    def get(self, key, default=None):
        # FIXME: for some reason, doesn't work:
        # self._shelf.get(key, default)
        #
        # instead:
        try:
            return self._shelf[key]
        except KeyError:
            return default


CURRENT_SESSION = None
def get_session():
    global CURRENT_SESSION
    if CURRENT_SESSION is None:
        CURRENT_SESSION = Session()
    return CURRENT_SESSION

# Make sure that we save the session on interpreter shutdown
@atexit_register
def _save_session():
    get_session().close()
