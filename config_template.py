#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Configuration parameters for brat

Author:     Pontus Stenetorp
Version:    2011-01-19
'''

# Contact email for users to use if the software encounters errors
ADMIN_CONTACT_EMAIL = CHANGE_ME

BASE_DIR = CHANGE_ME
DATA_DIR = CHANGE_ME
WORK_DIR = CHANGE_ME

# Below are commented out common configurations for BASE_DIR and DATA_DIR
'''
from os.path import dirname, join

BASE_DIR = dirname(__file__)
DATA_DIR = join(BASE_DIR, 'data')
WORK_DIR = join(BASE_DIR, 'work')
'''

# If ANNOTATION_LOG is defined, the system will log annotator actions into
# this file.

# ANNOTATION_LOG = join(WORK_DIR, 'annotation.log')

# TODO: Remove these when we have a back-end
USER_PASSWORD = {
    # Format:
    #   'USERNAME': 'PASSWORD',
    # Example, user `foo` and password `bar`:
    #   'foo': 'bar',
    }

# Enable additional debug output
DEBUG = False

# Log levels
LL_DEBUG, LL_INFO, LL_WARNING, LL_ERROR, LL_CRITICAL = range(5)
# If you are a developer you may want to turn on extensive server logging
LOG_LEVEL = LL_WARNING
'''
LOG_LEVEL = LL_DEBUG
'''

# If the source data is in Japanese enable word segmentation enable this flag
#   which is necessary for the `JAPANESE_TOKENIZATION` flag also in this file.
#
# To install support for Japanese tokenisation use the following command:
#
#   ( cd external && ./mecab.sh )
#
# Once installation is done set this variable to `True`.
'''
JAPANESE = True
'''

try:
    assert DATA_DIR != BACKUP_DIR
except NameError:
    pass # BACKUP_DIR most likely not defined

# It may be a good idea to limit the max number of results to a search
# as very high numbers can be demanding of both server and clients.
# (unlimited if not defined or <= 0)
MAX_SEARCH_RESULT_NUMBER = 1000

# If tokenization other than whitespace is desired, this can be used
'''
WHITESPACE_TOKENIZATION, PTBLIKE_TOKENIZATION, JAPANESE_TOKENIZATION = range(3)
TOKENIZATION = PTBLIKE_TOKENIZATION
'''

# If export to formats other than SVG is needed, the server must have
# a software capable of conversion like inkscape set up, and the
# following must be defined.
# (SETUP NOTE: at least Inkscape 0.46 requires the directory
# ".gnome2/" in the apache home directory and will crash if it doesn't
# exist.)
'''
SVG_CONVERSION_COMMANDS = [
    ('png', 'inkscape --export-area-drawing --without-gui --file=%s --export-png=%s'),
    ('pdf', 'inkscape --export-area-drawing --without-gui --file=%s --export-pdf=%s'),
    ('eps', 'inkscape --export-area-drawing --without-gui --file=%s --export-eps=%s'),
]
'''

# If web services providing automatic tagging are available, they
# can be made accessible by the UI by filling the following table.
# The format for tagger services is (ID, tagger name, tagger model, URL).
# The tagger name and model are used only in the UI as labels.
'''
NER_TAGGING_SERVICES = [
    ('Stanford-CoNLL-MUC', 'Stanford NER', 'CoNLL+MUC model', 'http://example.com:80/tagger/'),
    ('NERtagger-GENIA', 'NERtagger', 'GENIA model', 'http://example.com:8080/tagger/'),
]
'''
