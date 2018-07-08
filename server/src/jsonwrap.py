"""json wrapper to be used instead of a direct call.

Author:     Pontus Stenetorp    <pontus is s u-tokyo ac jp>
Version:    2011-04-21
"""

# use ultrajson if set up
try:
    from ujson import dumps as lib_dumps
    from ujson import loads as lib_loads
    # ultrajson doesn't have encoding

except ImportError:
    # fall back to native json if available
    from json import dumps as _lib_dumps
    from json import loads as _lib_loads

    # Wrap the loads and dumps to expect utf-8
    from functools import partial
    lib_dumps = partial(_lib_dumps, encoding='utf-8')  # , ensure_ascii=False)
    lib_loads = partial(_lib_loads, encoding='utf-8')  # , ensure_ascii=False)

# ensure_ascii[, check_circular[, allow_nan[, cls[, indent[, separators[,
# encoding


def dumps(dic):
    # ultrajson has neither sort_keys nor indent
    #     return lib_dumps(dic, sort_keys=True, indent=2)
    return lib_dumps(dic)


def loads(s):
    return lib_loads(s)

# TODO: Unittest that tries the import, encoding etc.
