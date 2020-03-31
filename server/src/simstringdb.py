# SIMSTRING_MISSING_ERROR = '''Error: failed to find the simstring library or executable.
# This library (or executable) is required for approximate string matching DB lookup.
# Please install simstring (and optionally its Python bindings) from
# http://www.chokkan.org/software/simstring/'''


Simstring = None
try:
    # Use the simstring library
    import simstringlib
    if hasattr(simstring, 'writer'):
        Simstring = simstringlib.SimstringLib
    else:
        del simstring
except ImportError:
    pass

if not Simstring:
    # Use the simstring executable
    import simstringexec
    Simstring = simstringexec.SimstringExec

# Usage:
#
# with Simstring('my_database', unicode=False, threshold=1.0) as ss:
#     print(ss.lookup('my_test_word'))
