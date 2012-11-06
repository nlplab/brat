#!/bin/sh

# Script for determining the (likely) apache user

apache_user=`ps aux | grep -v 'apache-user' | grep -v 'apache-group' | grep -v 'tomcat' | grep '[a]pache\|[h]ttpd' | cut -d ' ' -f 1 | grep -v '^root$' | head -n 1`

echo $apache_user
