#!/bin/sh

# Script for determining the (likely) apache group

apache_user=`./apache-user.sh`
apache_group=`groups $apache_user | head -n 1 | sed 's/ .*//'`

echo $apache_group
