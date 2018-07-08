#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

# Generates a web pages linking to visualizations of each document in
# a BioNLP ST 2011 Shared Task dataset.

import os
import sys

try:
    import argparse
except ImportError:
    from os.path import basename
    from sys import path as sys_path
    # We are most likely on an old Python and need to use our internal version
    sys_path.append(join_path(basename(__file__), '../server/lib'))
    import argparse

# Filename extensions that should be considered in selecting files to
# process.
known_filename_extensions = [".txt", ".a1", ".a2"]


def argparser():
    ap = argparse.ArgumentParser(
        description="Generate web page linking to visualizations of BioNLP ST documents.")
    ap.add_argument(
        "-v",
        "--visualizer",
        default="visualizer.xhtml",
        metavar="URL",
        help="Visualization script")
    ap.add_argument(
        "-s",
        "--staticdir",
        default="static",
        metavar="DIR",
        help="Directory containing static visualizations")
    ap.add_argument(
        "-d",
        "--dataset",
        default=None,
        metavar="NAME",
        help="Dataset name (derived from directory by default.)")
    ap.add_argument("directory", help="Directory containing ST documents.")
    ap.add_argument(
        "prefix",
        metavar="URL",
        help="URL prefix to prepend to links")
    return ap


def files_to_process(dir):

    try:
        toprocess = []
        for fn in os.listdir(dir):
            fp = os.path.join(dir, fn)
            if os.path.isdir(fp):
                print("Skipping directory %s" % fn, file=sys.stderr)
            elif os.path.splitext(fn)[1] not in known_filename_extensions:
                print("Skipping %s: unrecognized suffix" % fn, file=sys.stderr)
            else:
                toprocess.append(fp)
    except OSError as e:
        print("Error processing %s: %s" % (dir, e), file=sys.stderr)

    return toprocess


def print_links(files, arg, out=sys.stdout):
    # group by filename root (filename without extension)
    grouped = {}
    for fn in files:
        root, ext = os.path.splitext(fn)
        if root not in grouped:
            grouped[root] = []
        grouped[root].append(ext)

    # output in sort order
    sorted = sorted(grouped.keys())

    print("<table>", file=out)

    for root in sorted:
        path, fn = os.path.split(root)

        print("<tr>", file=out)
        print("  <td>%s</td>" % fn, file=out)

        # dynamic visualization
        print("  <td><a href=\"%s\">dynamic</a></td>" % (
            arg.prefix + arg.visualizer + "#" + arg.dataset + "/" + fn), file=out)

        # static visualizations
        print("  <td><a href=\"%s\">svg</a></td>" % (
            arg.prefix + arg.staticdir + "/svg/" + arg.dataset + "/" + fn + ".svg"), file=out)
        print("  <td><a href=\"%s\">png</a></td>" % (
            arg.prefix + arg.staticdir + "/png/" + arg.dataset + "/" + fn + ".png"), file=out)

        # data files
        for ext in known_filename_extensions:
            if ext in grouped[root]:
                print("  <td><a href=\"%s\">%s</a></td>" % (
                    arg.prefix + root + ext, ext[1:]), file=out)
            else:
                # missing
                print("  <td>-</td>", file=out)

        print("</tr>", file=out)

    print("</table>", file=out)


def main(argv=None):
    if argv is None:
        argv = sys.argv
    arg = argparser().parse_args(argv[1:])

    # derive dataset name from directory if not separately specified
    if arg.dataset is None:
        dir = arg.directory
        # strip trailing separators
        while dir[-1] == os.sep:
            dir = dir[:-1]
        arg.dataset = os.path.split(dir)[1]
        print("Assuming dataset name '%s', visualizations in %s" % (
            arg.dataset, os.path.join(arg.staticdir, arg.dataset)), file=sys.stderr)

    try:
        files = files_to_process(arg.directory)
        if files is None or len(files) == 0:
            print("No files found", file=sys.stderr)
            return 1
        print_header()
        print_links(files, arg)
        print_footer()
    except BaseException:
        print("Error processing %s" % arg.directory, file=sys.stderr)
        raise
    return 0


def print_header(out=sys.stdout):
    print("""<!DOCTYPE html PUBLIC '-//W3C//DTD XHTML 1.0 Strict//EN' 'http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd'>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head>
    <link rel="stylesheet" href="bionlp-st-11.css" type="text/css" />
    <meta http-equiv="Content-Type" content="text/html;charset=iso-8859-1"/>
    <title>BioNLP Shared Task 2011 - Data Visualization</title>
  </head>
<body>
  <div id="sites-chrome-everything" style="direction: ltr">
    <div id="sites-chrome-page-wrapper">

      <div id="sites-chrome-page-wrapper-inside">
	<div xmlns="http://www.w3.org/1999/xhtml" id="sites-chrome-header-wrapper">
	  <table id="sites-chrome-header" class="sites-layout-hbox" cellspacing="0">
	    <tr class="sites-header-primary-row">
	      <td id="sites-header-title">
		<div class="sites-header-cell-buffer-wrapper">
		  <h2>
		    <a href="https://sites.google.com/site/bionlpst/" dir="ltr">BioNLP Shared Task</a>

		  </h2>
		</div>
	      </td>
	    </tr>
	  </table>
	</div>
	<div id="sites-chrome-main-wrapper">
	  <div id="sites-chrome-main-wrapper-inside">
	    <table id="sites-chrome-main" class="sites-layout-hbox" cellspacing="0">
	      <tr>

		<td id="sites-canvas-wrapper">
		  <div id="sites-canvas">
		    <div xmlns="http://www.w3.org/1999/xhtml" id="title-crumbs" style="">
		    </div>
		    <h3 xmlns="http://www.w3.org/1999/xhtml" id="sites-page-title-header" style="" align="left">
		      <span id="sites-page-title" dir="ltr">BioNLP Shared Task 2011 Downloads</span>
		    </h3>
		    <div id="sites-canvas-main" class="sites-canvas-main">

		      <div id="sites-canvas-main-content">





			<!-- ##################################################################### -->
			<div id="main">
""", file=out)


def print_footer(out=sys.stdout):
    print("""		      </div>
		    </div>
		  </div>
		</td>
	      </tr>
	    </table>
	  </div>
	</div>
      </div>
    </div>
  </div>
</body>
</html>""", file=out)


if __name__ == "__main__":
    sys.exit(main())
