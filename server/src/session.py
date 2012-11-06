#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Session handling class.

Note: New modified version using pickle instead of shelve.

Author:     Goran Topic         <goran is s u-tokyo ac jp>
Author:     Pontus Stenetorp    <pontus is s u-tokyo ac jp>
Version:    2011-03-11
'''

from __future__ import with_statement

from Cookie import CookieError, SimpleCookie
from atexit import register as atexit_register
from datetime import datetime, timedelta
from hashlib import sha224
from os import makedirs, remove
from os.path import exists, dirname, join as path_join, isfile
from shutil import copy
from shutil import move
from tempfile import mkstemp

try:
    from cPickle import dump as pickle_dump, load as pickle_load
except ImportError:
    from pickle import dump as pickle_dump, load as pickle_load

from config import WORK_DIR

### Constants
CURRENT_SESSION = None
SESSION_COOKIE_KEY = 'sid'
# Where we store our session data files
SESSIONS_DIR=path_join(WORK_DIR, 'sessions')
EXPIRATION_DELTA = timedelta(days=30)
###


# Raised if a session is requested although not initialised
class NoSessionError(Exception):
    pass

# Raised if a session could not be stored on close
class SessionStoreError(Exception):
    pass

class SessionCookie(SimpleCookie):
    def __init__(self, sid=None):
        if sid is not None:
            self[SESSION_COOKIE_KEY] = sid

    def set_expired(self):
        self[SESSION_COOKIE_KEY]['expires'] = 0

    def set_sid(self, sid):
        self[SESSION_COOKIE_KEY] = sid

    def get_sid(self):
        return self[SESSION_COOKIE_KEY].value

    def hdrs(self):
        # TODO: can probably be done better
        hdrs = [('Cache-Control', 'no-store, no-cache, must-revalidate')]
        for cookie_line in self.output(header='Set-Cookie:',
                sep='\n').split('\n'):
            hdrs.append(tuple(cookie_line.split(': ', 1)))
        return tuple(hdrs)

    @classmethod
    def load(cls, cookie_data):
        cookie = SessionCookie()
        SimpleCookie.load(cookie, cookie_data)
        return cookie
    # TODO: Weave the headers into __str__


class Session(dict):
    def __init__(self, cookie):
        self.cookie = cookie
        sid = self.cookie.get_sid()
        self.init_cookie(sid)

    def init_cookie(self, sid):
        # Clear the cookie and set its defaults
        self.cookie.clear()

        self.cookie[SESSION_COOKIE_KEY] = sid
        self.cookie[SESSION_COOKIE_KEY]['path'] = ''
        self.cookie[SESSION_COOKIE_KEY]['domain'] = ''
        self.cookie[SESSION_COOKIE_KEY]['expires'] = (
                datetime.utcnow() + EXPIRATION_DELTA
                ).strftime('%a, %d %b %Y %H:%M:%S')
        # Protect against cookie-stealing JavaScript
        try:
            # Note: This will not work for Python 2.5 and older
            self.cookie[SESSION_COOKIE_KEY]['httponly'] = True
        except CookieError:
            pass

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def get_sid(self):
        return self.cookie.get_sid()

    def __str__(self):
        return 'Session(sid="%s", cookie="%s",  dict="%s")' % (
                self.get_sid(), self.cookie, dict.__str__(self), )


def get_session_pickle_path(sid):
    return path_join(SESSIONS_DIR, '%s.pickle' % (sid, ))

def init_session(remote_address, cookie_data=None):
    if cookie_data is not None:
        cookie = SessionCookie.load(cookie_data)
    else:
        cookie = None
 
    # Default sid for the session
    sid = sha224('%s-%s' % (remote_address, datetime.utcnow())).hexdigest()
    if cookie is None:
        cookie = SessionCookie(sid)
    else:
        try:
            cookie.get_sid()
        except KeyError:
            # For some reason the cookie did not contain a SID, set to default
            cookie.set_sid(sid)

    # Set the session singleton (there can be only one!)
    global CURRENT_SESSION
    ppath = get_session_pickle_path(cookie.get_sid())
    if isfile(ppath):
        # Load our old session data and initialise the cookie
        try:
            with open(ppath, 'rb') as session_pickle:
                CURRENT_SESSION = pickle_load(session_pickle)
            CURRENT_SESSION.init_cookie(CURRENT_SESSION.get_sid())
        except Exception, e:
            # On any error, just create a new session
            CURRENT_SESSION = Session(cookie)            
    else:
        # Create a new session
        CURRENT_SESSION = Session(cookie)

def get_session():
    if CURRENT_SESSION is None:
        raise NoSessionError
    return CURRENT_SESSION

def invalidate_session():
    global CURRENT_SESSION
    if CURRENT_SESSION is None:
        return

    # Set expired and remove from disk
    CURRENT_SESSION.cookie.set_expired()
    ppath = get_session_pickle_path(CURRENT_SESSION.get_sid())
    if isfile(ppath):
        remove(ppath)

def close_session():
    # Do we have a session to save in the first place?
    if CURRENT_SESSION is None:
        return

    try:
        makedirs(SESSIONS_DIR)
    except OSError, e:
        if e.errno == 17:
            # Already exists
            pass
        else:
            raise

    # Write to a temporary file and move it in place, for safety
    tmp_file_path = None
    try:
        _, tmp_file_path = mkstemp()
        with open(tmp_file_path, 'wb') as tmp_file:
            pickle_dump(CURRENT_SESSION, tmp_file)
        copy(tmp_file_path, get_session_pickle_path(CURRENT_SESSION.get_sid()))
    except IOError:
        # failed store: no permissions?
        raise SessionStoreError
    finally:
        if tmp_file_path is not None:
            remove(tmp_file_path)

def save_conf(config):
    get_session()['conf'] = config
    return {}
    
def load_conf():
    try:
        return {
                'config': get_session()['conf'],
                }
    except KeyError:
        return {}


if __name__ == '__main__':
    # Some simple sanity checks
    try:
        get_session()
        assert False
    except NoSessionError:
        pass

    # New "fresh" cookie session check
    init_session('127.0.0.1')
    
    try:
        session = get_session()
        session['foo'] = 'bar'
    except NoSessionError:
        assert False

    # Pickle check
    init_session('127.0.0.1')
    tmp_file_path = None
    try:
        _, tmp_file_path = mkstemp()
        session = get_session()
        session['foo'] = 'bar'
        with open(tmp_file_path, 'wb') as tmp_file:
            pickle_dump(session, tmp_file)
        del session

        with open(tmp_file_path, 'rb') as tmp_file:
            session = pickle_load(tmp_file)
            assert session['foo'] == 'bar'
    finally:
        if tmp_file_path is not None:
            remove(tmp_file_path)
