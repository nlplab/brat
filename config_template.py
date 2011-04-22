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

# Below are commented out common configurations for BASE_DIR and DATA_DIR
'''
from os.path import dirname, join

BASE_DIR = dirname(__file__)
DATA_DIR = join(BASE_DIR, 'data')
'''

# Enable additional debug output
DEBUG = False

# Contact email for users to use if the software encounters errors
ADMIN_CONTACT_EMAIL = CHANGE_ME
