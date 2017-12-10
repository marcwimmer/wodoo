#!/bin/bash

echo "Exporting default configuration to /etc_default"
rsync /etc/asterisk/ /opt/etc/asterisk/ -ar -delete

chown "$DEFAULT_USER":"$DEFAULT_USER" /opt/etc/asterisk -R
