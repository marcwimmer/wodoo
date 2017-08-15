#!/bin/bash
set -ex
[[ -z "$HOST" ]] && { echo 'HOST missing'; exit -1; }; 
[[ -z "$PORT" ]] && { echo 'PORT missing'; exit -1; };
sed -i "s/__HOST__/$HOST/g" /etc/nginx/sites-available/nginx.conf 
sed -i "s/__PORT__/$PORT/g" /etc/nginx/sites-available/nginx.conf
/usr/sbin/nginx -g 'daemon off;'
