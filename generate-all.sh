#!/bin/bash

# Special-purpose script for generating static HTML for visualization.
# Invokes generate-static.py for all Shared Task data directories in
# data/.

for d in data/BioNLP-ST_2011_* ; do
    rm -f static/${d##*/}.html
    python generate-static.py $d > static/${d##*/}.html
done
