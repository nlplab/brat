#!/usr/bin/env python

"""Generate a set of colours for a given set of input labels.

Author:     Pontus Stenetorp    <pontus stenetorp se>
Version:    2012-06-28
"""

# TODO: With some frequency information this could be done even more
#   intelligently, attempting to use the space optimally by keeping frequent
#   labels apart? Ultimately, we need some sort of desired distance measure.

from argparse import ArgumentParser, FileType
from colorsys import hls_to_rgb, rgb_to_hls
from sys import stdin, stdout


def _argparser():
    argparser = ArgumentParser()
    argparser.add_argument('-i', '--input', type=FileType('r'), default=stdin)
    argparser.add_argument(
        '-o',
        '--output',
        type=FileType('w'),
        default=stdout)
    argparser.add_argument('-c', '--visual-conf', action='store_true')
    return argparser


def main(args):
    argp = _argparser().parse_args(args[1:])
    lbls = [l.rstrip('\n') for l in argp.input]
    # Note: Do some testing before allowing too big an input
    assert len(lbls) <= 100, 'currently not supporting more than a hundred'

    hue, lightness, saturation = rgb_to_hls(1.0, 0.0, 0.0)
    # Gently bump the lightness to produce softer colours
    lightness += 0.05
    hue_step = 1.0 / len(lbls)

    for lbl in lbls:
        hex_output = '#{:02x}{:02x}{:02x}'.format(
            *[int(255 * e) for e in hls_to_rgb(hue, lightness, saturation)])

        if argp.visual_conf:
            argp.output.write('{}\tbgColor:{}'.format(lbl, hex_output))
        else:
            argp.output.write(hex_output)
        argp.output.write('\n')

        hue += hue_step
    return 0


if __name__ == '__main__':
    from sys import argv
    exit(main(argv))
