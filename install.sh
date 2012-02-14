#!/bin/sh

# Install script for brat server

# defaults

WORK_DIR=work
DATA_DIR=data
CONFIG_TEMPLATE=config_template.py
CONFIG=config.py

# Absolute data and work paths

base_dir=`dirname $0 | xargs readlink -f`

work_dir_abs="$base_dir/$WORK_DIR"
data_dir_abs="$base_dir/$DATA_DIR"

# Ask details for config

while true; do
    echo "Please enter a brat username"
    read user_name
    if [ -n "$user_name" ]; then
	break
    fi
done

while true; do
    echo "Please enter a brat password (this shows on screen)"
    read password
    if [ -n "$password" ]; then
	break
    fi
done

echo "Please enter the administrator contact email"
read admin_email

# Put a configuration in place.

(echo "# This is an automatically generated configuration."
cat "$base_dir/$CONFIG_TEMPLATE" | sed \
    -e 's|\(ADMIN_CONTACT_EMAIL = \).*|\1'\'$admin_email\''|' \
    -e 's|\(BASE_DIR = \).*|\1'\'$base_dir\''|' \
    -e 's|\(DATA_DIR = \).*|\1'\'$data_dir_abs\''|' \
    -e 's|\(WORK_DIR = \).*|\1'\'$work_dir_abs\''|' \
    -e 's|\(USER_PASSWORD *= *{.*\)|\1\n    '\'"$user_name"\'': '\'"$password"\'',|') > "$base_dir/$CONFIG"

# Create directories

mkdir -p $work_dir_abs
mkdir -p $data_dir_abs

# Try to determine apache group

apache_user=`ps aux | grep '[a]pache' | cut -d ' ' -f 1 | grep -v '^root$' | head -n 1`
apache_group=`groups $apache_user | head -n 1 | sed 's/ .*//'`

# Make $work_dir_abs and $data_dir_abs writable by apache

if [ -n "$apache_group" ] ; then
    echo "Assigning owner of \"$work_dir_abs/\" and \"$data_dir_abs/\" directories to apache ($apache_group):"
    echo "(this requires sudo; please enter your password)"    
    while true; do
	sudo chgrp -R $apache_group $data_dir_abs $work_dir_abs
	RETVAL=$?
	if [ $RETVAL -eq 0 ]; then
	    break
	fi
    done
    chmod -R g+rwx $data_dir_abs $work_dir_abs
else
    echo "WARNING: failed to determine apache group."
    echo "Setting global read and write permissions to \"$work_dir_abs/\" and \"$data_dir_abs/\" directories"
    echo "(you may wish to consider fixing this manually)"
    chmod -R 777 $data_dir_abs $work_dir_abs
fi

# Extract the most important library dependencies.

( cd server/lib && tar xfz simplejson-2.1.5.tar.gz )

# We really should check, but ...

echo "Done! Please try your installation."
