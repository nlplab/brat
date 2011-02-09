#!/usr/bin/env python

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
    for s, type, duration in __pending_messages:
        # TODO: multiple messages
        json_dict['message'] = s
    __pending_messages = []

