#!/home/users/pontus/local/bin/python

'''
Entry for cgi calls to the brat application. This is a simple wrapper that
only imports a bare minimum and ensures that the web-based UI gets a proper
response even when the server crashes. If in debug mode it returns any errors
that occur using the established messaging API.

This file should stay compatible with Python 2.3 and upwards until it has done
the version checking in order to assure that we can return sensible results
to the user and administrators.

Author:     Pontus  Stenetorp   <pontus is s u tokyo ac jp>
Version:    2010-02-07
'''

from sys import version_info

### Constants
# This handling of version_info is strictly for backwards compability
PY_VER_STR = '%d.%d.%d-%s-%d' % tuple(version_info)
INVALID_PY_JSON = '''
{
  "error": "Incompatible Python version (%s), 2.7 or above is supported",
  "duration": -1
}
''' % PY_VER_STR
CONF_FNAME = 'config.py'
CONF_TEMPLATE_FNAME = 'config_template.py'
###

def _miss_var_msg(var):
    #TODO: DOC!
    return ('Missing variable "{var}" in {config}, make sure that you have '
            'not made any errors to your configurations and to start over '
            'copy the template file {template} to {config} in your '
            'installation directory and edit it to suit your environment'
            ).format(var=var, config=CONF_FNAME, template=CONF_TEMPLATE_FNAME)

def _miss_config_msg():
    #TODO: DOC!
    return ('Missing file {config} in the installation dir, if this is a new '
            'installation copy the template file {template} to {config} in '
            'your installation directory and edit it to suit your environment'
            ).format(config=CONF_FNAME, template=CONF_TEMPLATE_FNAME)

def _dumps(dic):
    '''
    Create a json dumps string out of a dictionary. Used for consistent usage
    within this file.

    Arguments:
    dic -- dictionary to convert into json
    '''
    from json import dumps
    return dumps(dic, sort_keys=True, indent=2)

def main(args):
    # Check the Python version, if it is incompatible print a manually crafted
    # json error. This needs to be updated manually as the protocol changes.
    if version_info[0] != 2 or version_info[1] < 7:
        print 'Content-Type: application/json\n'
        print INVALID_PY_JSON
        return -1
    
    # From now on we know we have access to _dumps
   
    # Do configuration checking and importing
    from sys import path
    from copy import deepcopy
    from os.path import dirname
    # Reset the path to force config.py to be in this dir (could be hacked
    #       using __init__.py, but we can be monkey-patched anyway)
    orig_path = deepcopy(path)
    # Can't you empty in O(1) instead of O(N)?
    while path:
        path.pop()
    path.append(dirname(__file__))
    # Check if we have a config, otherwise whine
    try:
        import config
        del config
    except ImportError:
        path.extend(orig_path)
        print 'Content-Type: application/json\n'
        print _dumps(
                {
                    'error': _miss_config_msg(),
                    'duration': -1,
                }
                )
        raise
    # Try importing the config entries we need
    try:
        from config import DEBUG
    except ImportError:
        path.extend(orig_path)
        print 'Content-Type: application/json\n'
        print _dumps(
                {
                    # Keep this string up-to-date
                    'error': _miss_var_msg('DEBUG'),
                    'duration': -1,
                }
                )
        raise
    try:
        from config import ADMIN_CONTACT_EMAIL
    except ImportError:
        path.extend(orig_path)
        print 'Content-Type: application/json\n'
        print _dumps(
                {
                    # Keep this string up-to-date
                    'error': _miss_var_msg('ADMIN_CONTACT_EMAIL'),
                    'duration': -1,
                }
                )
        raise
    # Remove our entry to the path
    path.pop()
    # Then restore it
    path.extend(orig_path)

    try:
        # Make the actual call to the server
        from ajaxserver import serve
        return serve(args)
    except Exception, e:
        # Catches even an interpreter crash
        if DEBUG:
            # Send back the stacktrack as json
            from traceback import print_exc
            try:
                from cStringIO import StringIO
            except ImportError:
                from StringIO import StringIO

            buf = StringIO()
            print_exc(file=buf)
            buf.seek(0)
            print 'Content-Type: application/json\n'
            error_msg = '<br/>'.join((
            'Server Python crash, stacktrace is:\n',
            buf.read())).replace('\n', '\n<br/>\n')
            print _dumps(
                    {
                        'error': error_msg,
                        'duration': -1,
                    })
        else:
            # Give the user an error message
            from time import time
            # Use the current time since epoch as an id for later log look-up
            error_msg = ('The server encountered a serious error, '
                    'please contact the administrators at {} '
                    'and give the id #{}'
                    ).format(ADMIN_CONTACT_EMAIL, int(time()))
            print 'Content-Type: application/json\n'
            print _dumps(
                    {
                        'error': error_msg,
                        'duration': -1,
                    })
        # Allow the exception to fall through so it is logged by Apache
        raise
    return -1

if __name__ == '__main__':
    from sys import argv, exit
    exit(main(argv))
