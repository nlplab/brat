#!/bin/sh
 
current_time=$(date "+%Y-%m-%d-%H-%M-%S")

output_filename="$current_time-data-backup.tar.gz"

tar -cvzf $output_filename data/