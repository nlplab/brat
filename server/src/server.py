#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; -*- 
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Main entry for the brat server, ensures integrity, handles dispatch and
processes potential exceptions before returning them to be sent as responses.

NOTE(S):

* Defer imports until failures can be catched

Author:     Pontus  Stenetorp   <pontus is s u tokyo ac jp>
Version:    2010-09-29
'''


class InstallationIntegrityError(Exception):
    pass


# TODO: Ensure installation integrity
def _integrity_check():
    pass


class ConfigurationError(Exception):
    pass


# TODO: Ensure installation configuration
def _config_check():
    pass

# TODO: Returns json data or None!
def serve(params, client_ip, client_hostname):
    # At this stage we can not get any cookie data, wait-for-it
    cookie_hdrs = None

    # TODO: SANITY!
    # TODO: Enable logging!

    # We can now get the cookie
    from session import get_session
    cookie_hdrs = get_session().get_cookie_hdrs()

    ### TODO: Move around these imports
    from common import ProtocolError, NoPrintJSONError
    from jsonwrap import dumps
    from message import Messager
    ###

    from dispatch import dispatch
    try:
        json_dic = dispatch(params, client_ip, client_hostname)

        response_data = (('Content-Type', 'application/json'),
                dumps(Messager.output_json(json_dic)))
    except ProtocolError, e:
        # Internal error, only reported to client not to log
        json_dic = {}
        e.json(json_dic)

        # Add a human-readable version of the error
        err_str = str(e)
        if not err_str:
            Messager.error(e)
        
        response_data = (('Content-Type', 'application/json'),
                dumps(Messager.output_json(json_dic)))
    except NoPrintJSONError, e:
        # TODO: Re-wire so that the error holds the content
        assert False, 'Not implemented!'

    # TODO: Should the cookie always go back even upon errors?
    return (cookie_hdrs, response_data)

# TODO: Small test
if __name__ == '__main__':
    from sys import argv, exit
    exit(main(argv))
