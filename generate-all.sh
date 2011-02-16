# -*- Mode: Shell; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=sh ts=4 sw=4 sts=4 autoindent:

#!/bin/bash

# Special-purpose script for generating static HTML for visualization.
# Invokes generate-static.py for all Shared Task data directories in
# data/.

for d in data/BioNLP-ST_2011_* ; do
    rm -f static/${d##*/}.html
    python generate-static.py $d > static/${d##*/}.html
done
