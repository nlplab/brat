#!/bin/bash

DATADIR=${1:-data} # Argument 1, defaulting to 'data' if not set

sudo find $DATADIR -not -name .stats_cache -type f -exec chown $USER:www-data {} \; -exec chmod 660 {} \; # ug=rw, o=
sudo find $DATADIR -type d -exec sudo chown $USER:www-data {} \; -exec chmod 770 {} \; # ug=rwx, o=
sudo find $DATADIR -name .stats_cache -exec chown www-data:www-data {} \; -exec chmod 644 {} \; # u=rw, ro=r
