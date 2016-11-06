#!/bin/bash
set -x
touch /tmp/debugging

# install marcvim

pkill -9 -f stasis

echo "Starting Stasis...."
cd /opt/src/asterisk_ari/stasis

python stasis.py
