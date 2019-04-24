#!/usr/bin/env python

"""Penn TreeBank escaping.

Author:     Pontus Stenetorp    <pontus stenetorp se>
Version:    2011-09-12
"""

# Constants
# From: To
PTB_ESCAPES = {
    '(': '-LRB-',
    ')': '-RRB-',
    '[': '-LSB-',
    ']': '-RSB-',
    '{': '-LCB-',
    '}': '-RCB-',
    '/': '\/',
    '*': '\*',
}
###


def escape(s):
    r = s
    for _from, to in PTB_ESCAPES.items():
        r = r.replace(_from, to)
    return r


def unescape(s):
    r = s
    for _from, to in PTB_ESCAPES.items():
        r = r.replace(to, _from)
    return r


def main(args):
    from argparse import ArgumentParser
    from sys import stdin, stdout

    # TODO: Doc!
    argparser = ArgumentParser()
    argparser.add_argument('-u', '--unescape', action='store_true')
    argp = argparser.parse_args(args[1:])

    for line in (l.rstrip('\n') for l in stdin):
        if argp.unescape:
            r = unescape(line)
        else:
            r = escape(line)
        stdout.write(r)
        stdout.write('\n')


if __name__ == '__main__':
    from sys import argv
    exit(main(argv))
