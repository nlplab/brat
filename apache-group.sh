#!/bin/sh

# Script for determining the (likely) apache group

apache_user=`ps aux | grep '[a]pache' | cut -d ' ' -f 1 | grep -v '^root$' | head -n 1`
apache_group=`groups $apache_user | head -n 1 | sed 's/ .*//'`

echo $apache_group
