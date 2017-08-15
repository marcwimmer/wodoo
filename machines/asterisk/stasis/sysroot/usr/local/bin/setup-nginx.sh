#!/bin/bash
set -ex
sed -i "s/__PROXY_PORT_IN__/$PROXY_PORT_IN/g" /etc/nginx/sites-available/nginx.conf
sed -i "s/__PROXY_PORT_OUT__/$PROXY_PORT_OUT/g" /etc/nginx/sites-available/nginx.conf
pkill -f nginx || true
/usr/sbin/nginx
