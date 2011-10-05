#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Wrapper for safely importing Messager with a fallback that will
get _something_ to the user even if Messager itself breaks.
'''

try:
    from realmessage import Messager
except:
    from sosmessage import SosMessager as Messager
