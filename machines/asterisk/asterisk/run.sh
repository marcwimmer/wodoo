#!/bin/bash

# get latest config
cd /etc/asterisk
git checkout deploy -f
git clean -x -d -f
git pull


ifconfig
rsync -ar /opt/forced_asterisk/ /etc/asterisk/
/usr/sbin/asterisk -v > /dev/null
