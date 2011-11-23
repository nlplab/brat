#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Configuration parameters for brat

Author:     Pontus Stenetorp
Version:    2011-01-19
'''

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

# Contact email for users to use if the software encounters errors
ADMIN_CONTACT_EMAIL = CHANGE_ME

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

# If tokenization other than whitespace is desired, this can be used
'''
WHITESPACE_TOKENIZATION, PTBLIKE_TOKENIZATION, JAPANESE_TOKENIZATION = range(3)
TOKENIZATION = PTBLIKE_TOKENIZATION
'''
