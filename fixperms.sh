#!/bin/bash

sudo find data -not -name .stats_cache -type f -exec chown $USER:www-data {} \; -exec chmod 660 {} \; # ug=rw, o=
sudo find data -type d -exec sudo chown $USER:www-data {} \; -exec chmod 770 {} \; # ug=rwx, o=
sudo find data -name .stats_cache -exec chown www-data:www-data {} \; -exec chmod 644 {} \; # u=rw, ro=r
