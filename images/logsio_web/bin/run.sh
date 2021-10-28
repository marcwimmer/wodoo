#!/bin/bash
set -e
bin/log.io-server  & 
sleep 3
echo "Starting io file input"
python3 /usr/local/bin/setup_container_logs_to_watch.py || exit -1
log.io-file-input