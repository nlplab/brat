#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Server-to-client messaging-related functionality for
Brat Rapid Annotation Tool (brat)
'''

# TODO: make this minimal implmentation into a proper messaging
# interface

__pending_messages = []

def display_message(s, type='info', duration=3):
    global __pending_messages
    __pending_messages.append((s, type, duration))

def add_messages_to_json(json_dict):
    global __pending_messages
    if 'messages' not in json_dict:
        json_dict['messages'] = []
    json_dict['messages'] += __pending_messages
    __pending_messages = []

