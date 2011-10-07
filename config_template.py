#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Configuration parameters

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
DATA_DIR = join(BASE_DIR, RELATIVE_PATH_TO_DATA_DIR)
WORK_DIR = join(BASE_DIR, RELATIVE_PATH_TO_WORK_DIR)
'''

USER_PASSWORD = {
        CHANGE_ME : CHANGE_ME
        }

# Enable additional debug output
DEBUG = False

# Contact email for users to use if the software encounters errors
ADMIN_CONTACT_EMAIL = CHANGE_ME

DEBUG, INFO, WARNING, ERROR, CRITICAL = range(5)
# If you are developing you may want to turn on extensive server logging
LOG_LEVEL = WARNING
'''
LOG_LEVEL = DEBUG
'''

# If the source data is in Japanese enable word segmentation
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

