#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
SVG saving and storage functionality.

Author:     Pontus Stenetorp    <pontus is s u-tokyo ac jp>
Author:     Goran Topic         <goran is s u-tokyo ac jp>
Version:    2011-04-22
'''

# TODO: Can we verify somehow that what we are getting is actually an svg?
# TODO: Limits to size? Or inherent from HTTP?

from __future__ import with_statement

from os.path import join as path_join
from os.path import isfile

from common import ProtocolError, NoPrintJSONError
from config import BASE_DIR
from message import display_message
from session import get_session

### Constants
# TODO: We really need a work directory
SVG_DIR = path_join(BASE_DIR, 'svg')
# TODO: These constants most likely don't belong here
CSS_PATH = path_join(BASE_DIR, 'style.css')
GRAYSCALE_CSS_PATH = path_join(BASE_DIR, 'style_grayscale.css')
###


class UnknownSVGVersionError(ProtocolError):
    def __init__(self, unknown_version):
        self.unknown_version = unknown_version

    def json(self, json_dic):
        json_dic['exception'] = 'unknownSVGVersion'
        display_message('Version "%s" is not a valid version'
                % self.unknown_version, 'error')
        return json_dic


class NoSVGError(ProtocolError):
    def __init__(self, version):
        self.version = version

    def json(self, json_dic):
        json_dic['exception'] = 'noSVG'
        directory('SVG with version "%s" does not exist "%s"'
                % (self.version, ), 'error')
        return json_dic


def _save_svg(svg, colour=True):
    if colour:
        css_path = CSS_PATH
    else:
        css_path = GRAYSCALE_CSS_PATH

    svg_path = _svg_path(colour=colour)

    with open(svg_path, 'w') as svg_file:
        svg_file.write('<?xml version="1.0" standalone="no"?>'
                '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" '
                '"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">')
        defs = svg.find('</defs>')

        with open(css_path, 'r') as css_file:
            css = css_file.read()

        if defs != -1:
            css = '<style type="text/css"><![CDATA[' + css + ']]></style>'
            svg = svg[:defs] + css + svg[defs:]
            svg_file.write(svg)
        else:
            # TODO: Always print this? Use an exception?
            # XXX: When does this actually happen?
            display_message("Error: bad SVG!", "error", -1)

def _svg_path(colour=True):
    base_path = path_join(SVG_DIR, get_session().sid)
    if colour:
        return base_path + '_colour.svg'
    else:
        return base_path + '_greyscale.svg'

def store_svg(svg):
    _save_svg(svg)
    _save_svg(svg, colour=False)
    return {}

def retrieve_svg(document, version):
    if version == 'colour':
        svg_path = _svg_path()
    elif version == 'greyscale':
        svg_path = _svg_path(colour=False)
    else:
        raise UnknownSVGVersionError(version)

    if not isfile(svg_path):
        raise NoSVGError(version)

    print 'Content-Type: image/svg+xml'
    print 'Content-Disposition: inline; filename=' + document + '.svg\n'
    with open(svg_path, 'r') as svg_file:
        print svg_file.read()
    print
    # Bail out with a hack since we violated the protocol
    raise NoPrintJSONError
