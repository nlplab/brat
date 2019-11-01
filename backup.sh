#!/bin/sh
 
current_time=$(date "+%Y-%m-%d-%H-%M-%S")
script_path="`dirname \"$0\"`"

output_filename="$script_path/$current_time-data-backup.tar.gz"


echo "$script_path"/data/
tar -cvzf $output_filename "$script_path"/data/