'''
json wrapper to be used instead of a direct call.

Author:     Pontus Stenetorp    <pontus is s u-tokyo ac jp>
Version:    2011-04-21
'''

from functools import partial

try:
    from json import dumps as _lib_dumps
    from json import loads as _lib_loads
except ImportError:
    # We are on an older Python, use our included lib
    from sys import path as sys_path
    from os.path import join as path_join
    from os.path import dirname

    sys_path.append('../lib/simplejson-2.1.5')

    from simplejson import dumps as _lib_dumps
    from simplejson import loads as _lib_loads

# Wrap the loads and dumps to expect utf-8
lib_dumps = partial(_lib_dumps, encoding='utf-8')#, ensure_ascii=False)
lib_loads = partial(_lib_loads, encoding='utf-8')#, ensure_ascii=False)

#ensure_ascii[, check_circular[, allow_nan[, cls[, indent[, separators[, encoding

def dumps(dic):
    return lib_dumps(dic, sort_keys=True, indent=2)

def loads(s):
    return lib_loads(s)

# TODO: Unittest that tries the import, encoding etc.
