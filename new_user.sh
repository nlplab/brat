#!/bin/sh

while true; do
echo 'Please enter the new user name that you want to use when logging into brat:'
read user_name
if [ -n "$user_name" ]; then
    break
fi
done
while true; do
echo "Please enter a brat password (this shows on screen):"
read password
if [ -n "$password" ]; then
    password=$(python -c 'from hashlib import pbkdf2_hmac; from base64 import b64encode; print b64encode(pbkdf2_hmac("sha256", u"'$password'".encode("utf-8"), u"'$user_name'".encode("utf-8"), 30000))')
    break
fi
done

echo "Place the following line in USER_PASSWORD in the config.py file"
echo "'$user_name': '$password',"
