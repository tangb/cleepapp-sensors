#!/bin/bash

# exit when any command fails
set -e
# keep track of the last executed command
trap 'last_command=$current_command; current_command=$BASH_COMMAND' DEBUG
# echo an error message before exiting
trap 'echo "\"${last_command}\" command failed with exit code $?."' ERR

# main
apt-get update
apt-get -y -q install wiringpi
chmod +x dht22
cp -f dht22 /usr/local/bin/

