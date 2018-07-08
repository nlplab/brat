#!/usr/bin/env python

"""Initiate a tutorial session.

Author:     Goran Topic
            Sampo Pyysalo
            Pontus Stenetorp
Version:    2012-11-12
"""

from sys import path as sys_path
from os.path import join as path_join
from os.path import dirname, isdir
from shutil import copytree, rmtree
from os import environ, makedirs, errno
from cgi import FieldStorage
import re

sys_path.append(path_join(dirname(__file__), 'server/src'))
from session import init_session, get_session

from config import DATA_DIR

# Tutorials have to be enabled explicitly since it modifies the disk
try:
    from config import TUTORIALS
except ImportError:
    TUTORIALS = False

if not TUTORIALS:
    print('Content-Type: text/plain')
    print('')
    print('Tutorials disabled on this server, please enable it in config.py')
    print('')
    print('')
    exit(0)

TUTORIAL_BASE = '.tutorials'
TUTORIAL_START = '000-introduction'
TUTORIAL_DATA_DIR = DATA_DIR
TUTORIAL_SKELETON = 'example-data/tutorials/'
DEFAULT_TUTORIAL_TYPE = 'news'


def mkdir_p(path):
    try:
        makedirs(path)
    except OSError as x:
        if x.errno == errno.EEXIST and isdir(path):
            pass
        else:
            raise


try:
    remote_addr = environ['REMOTE_ADDR']
except KeyError:
    remote_addr = None
try:
    cookie_data = environ['HTTP_COOKIE']
except KeyError:
    cookie_data = None

params = FieldStorage()

if 'type' in params:
    tutorial_type = str(params.getvalue('type'))
else:
    tutorial_type = DEFAULT_TUTORIAL_TYPE
if 'overwrite' in params:
    overwrite = str(params.getvalue('overwrite'))
else:
    overwrite = False
# security check; don't allow arbitrary path specs for copytree
assert re.match(r'^[a-zA-Z0-9_-]+$', tutorial_type)

init_session(remote_addr, cookie_data=cookie_data)
_id = str(abs(hash(get_session().get_sid())))
reldir = path_join(TUTORIAL_BASE, '.' + _id)
userdir = path_join(TUTORIAL_DATA_DIR, reldir)
tutorial_dir = path_join(userdir, tutorial_type)

if not isdir(tutorial_dir) or overwrite:
    mkdir_p(userdir)
    if isdir(tutorial_dir) and overwrite:
        rmtree(tutorial_dir)
    copytree(path_join(TUTORIAL_SKELETON, tutorial_type), tutorial_dir)

start = path_join(reldir, tutorial_type, TUTORIAL_START)

print('Content-Type: text/plain')
print('Refresh: 0; url=index.xhtml#/%s' % start)
print('')
print('')
