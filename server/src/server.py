#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; -*- 
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Main entry for the stav server, ensures integrity, handles dispatch and
processes potential exceptions before returning them to be sent as responses.

NOTE(S):

* Defer imports until failures can be catched
* Stay compatible with Python 2.3 until we verify the Python version

Author:     Pontus  Stenetorp   <pontus is s u tokyo ac jp>
Version:    2010-09-29
'''

# Standard library version
from os.path import abspath
from os.path import join as path_join
from sys import version_info, stderr
from time import time

### Constants
# This handling of version_info is strictly for backwards compability
PY_VER_STR = '%d.%d.%d-%s-%d' % tuple(version_info)
REQUIRED_PY_VERSION_MAJOR = 2
REQUIRED_PY_VERSION_MINOR = 5
JSON_HDR = ('Content-Type', 'application/json')
CONF_FNAME = 'config.py'
CONF_TEMPLATE_FNAME = 'config_template.py'
###


class PermissionError(Exception):
    pass


# TODO: Possibly check configurations too
# TODO: Extend to check __everything__?
def _permission_check():
    from os import access, R_OK, W_OK
    from config import DATA_DIR, WORK_DIR
    from jsonwrap import dumps
    from message import Messager

    if not access(WORK_DIR, R_OK | W_OK):
        Messager.error((('Work dir: "%s" is not read-able and ' % WORK_DIR) +
                'write-able by the server'), duration=-1)
        raise PermissionError
    
    if not access(DATA_DIR, R_OK):
        Messager.error((('Data dir: "%s" is not read-able ' % DATA_DIR) +
                'by the server'), duration=-1)
        raise PermissionError


class ConfigurationError(Exception):
    pass


# Error message template functions
def _miss_var_msg(var):
    return ('Missing variable "%s" in %s, make sure that you have '
            'not made any errors to your configurations and to start over '
            'copy the template file %s to %s in your '
            'installation directory and edit it to suit your environment'
            ) % (var, CONF_FNAME, CONF_TEMPLATE_FNAME, CONF_FNAME)

def _miss_config_msg():
    return ('Missing file %s in the installation dir. If this is a new '
            'installation, copy the template file %s to %s in '
            'your installation directory ("cp %s %s") and edit '
            'it to suit your environment.'
            ) % (CONF_FNAME, CONF_TEMPLATE_FNAME, CONF_FNAME, CONF_FNAME,
                CONF_TEMPLATE_FNAME)

# Check for existance and sanity of the configuration
def _config_check():
    from message import Messager
    
    from sys import path
    from copy import deepcopy
    from os.path import dirname
    # Reset the path to force config.py to be in the root (could be hacked
    #       using __init__.py, but we can be monkey-patched anyway)
    orig_path = deepcopy(path)
    # Can't you empty in O(1) instead of O(N)?
    while path:
        path.pop()
    path.append(path_join(abspath(dirname(__file__)), '../..'))
    # Check if we have a config, otherwise whine
    try:
        import config
        del config
    except ImportError, e:
        path.extend(orig_path)
        # "Prettiest" way to check specific failure
        if e.message == 'No module named config':
            Messager.error(_miss_config_msg(), duration=-1)
        else:
            Messager.error(_get_stack_trace(), duration=-1)
        raise ConfigurationError
    # Try importing the config entries we need
    try:
        from config import DEBUG
    except ImportError:
        path.extend(orig_path)
        Messager.error(_miss_var_msg('DEBUG'), duration=-1)
        raise ConfigurationError
    try:
        from config import ADMIN_CONTACT_EMAIL
    except ImportError:
        path.extend(orig_path)
        Messager.error(_miss_var_msg('ADMIN_CONTACT_EMAIL'), duration=-1)
        raise ConfigurationError
    # Remove our entry to the path
    path.pop()
    # Then restore it
    path.extend(orig_path)

# Convert internal log level to logging log level
def _convert_log_level(log_level):
    import config
    import logging
    if log_level == config.DEBUG:
        return logging.DEBUG
    elif log_level == config.INFO:
        return logging.INFO
    elif log_level == config.WARNING:
        return logging.WARNING
    elif log_level == config.ERROR:
        return logging.ERROR
    elif log_level == config.CRITICAL:
        return logging.CRITICAL
    else:
        assert False, 'Should not happen'

def _safe_serve(params, client_ip, client_hostname):
    from common import ProtocolError, NoPrintJSONError
    from config import WORK_DIR
    from dispatch import dispatch
    from jsonwrap import dumps
    from logging import basicConfig as log_basic_config
    from message import Messager
    from session import get_session

    # Enable logging
    try:
        from config import LOG_LEVEL
        log_level = _convert_log_level(LOG_LEVEL)
    except ImportError:
        from logging import WARNING as LOG_LEVEL_WARNING
        log_level = LOG_LEVEL_WARNING
    log_basic_config(filename=path_join(WORK_DIR, 'server.log'),
            level=log_level)

    # Session information is now available
    cookie_hdrs = get_session().get_cookie_hdrs()

    try:
        # Dispatch the request
        json_dic = dispatch(params, client_ip, client_hostname)
        response_data = ((JSON_HDR, ), dumps(Messager.output_json(json_dic)))
    except ProtocolError, e:
        # Internal error, only reported to client not to log
        json_dic = {}
        e.json(json_dic)

        # Add a human-readable version of the error
        err_str = str(e)
        if err_str != '':
            Messager.error(err_str)

        response_data = ((JSON_HDR, ), dumps(Messager.output_json(json_dic)))
    except NoPrintJSONError, e:
        # Terrible hack to serve other things than JSON
        response_data = (e.hdrs, e.data)

    return (cookie_hdrs, response_data)

# Programmatically access the stack-trace
def _get_stack_trace():
    from traceback import print_exc
    
    try:
        from cStringIO import StringIO
    except ImportError:
        from StringIO import StringIO

    # Getting the stack-trace requires a small trick
    buf = StringIO()
    print_exc(file=buf)
    buf.seek(0)
    return buf.read()

# Encapsulate an interpreter crash
def _server_crash(cookie_hdrs, e):
    from config import ADMIN_CONTACT_EMAIL, DEBUG
    from jsonwrap import dumps
    from message import Messager

    stack_trace = _get_stack_trace()

    if DEBUG:
        # Send back the stack-trace as json
        error_msg = '\n'.join(('Server Python crash, stack-trace is:\n',
            stack_trace))
        Messager.error(error_msg, duration=-1)
    else:
        # Give the user an error message
        # Use the current time since epoch as an id for later log look-up
        error_msg = ('The server encountered a serious error, '
                'please contact the administrators at %s '
                'and give the id #%d'
                ) % (ADMIN_CONTACT_EMAIL, int(time()))
        Messager.error(error_msg, duration=-1)

    # Print to stderr so that the exception is logged by the webserver
    print >> stderr, stack_trace

    json_dic = {
            'exception': True,
            }
    return (cookie_hdrs, ((JSON_HDR, ), dumps(Messager.output_json(json_dic))))

# Serve the client request
def serve(params, client_ip, client_hostname):
    # At this stage we can not get any cookie data, wait-for-it
    cookie_hdrs = None

    # Do we have a Python version compatibly with our libs?
    if (version_info[0] != REQUIRED_PY_VERSION_MAJOR or
            version_info[1] < REQUIRED_PY_VERSION_MINOR):
        # Bail with hand-writen JSON, this is very fragile to protocol changes
        return cookie_hdrs, ((JSON_HDR, ),
                ('''
{
  "messages": [
    [
      "Incompatible Python version (%s), %d.%d or above is supported",
      "error",
      -1
    ]
  ]
}
                ''' % (PY_VER_STR, REQUIRED_PY_VERSION_MAJOR,
                    REQUIRED_PY_VERSION_MINOR)).strip())

    # We can now safely use json and Messager
    from jsonwrap import dumps
    from message import Messager
    
    try:
        _config_check()
    except ConfigurationError:
        return cookie_hdrs, ((JSON_HDR, ), dumps(Messager.output_json({})))
    # We can now safely read the config
    from config import DEBUG

    try:
        _permission_check()
    except PermissionError:
        return cookie_hdrs, ((JSON_HDR, ), dumps(Messager.output_json({})))

    try:
        # Safe region, can throw any exception, has verified installation
        return _safe_serve(params, client_ip, client_hostname)
    except BaseException, e:
        # Handle the server crash
        return _server_crash(cookie_hdrs, e)
