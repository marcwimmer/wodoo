#!/bin/bash
set -ex
conffile=/etc/nginx/sites-enabled/default
sed -i "s/__PROXY_PORT_IN__/$PROXY_PORT_IN/g" $conffile
sed -i "s/__PROXY_PORT_OUT__/$PROXY_PORT_OUT/g" $conffile
pkill -f nginx || true
/usr/sbin/nginx
