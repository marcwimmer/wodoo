#!/bin/bash
set -e

echo 'setting up nginx conf'
cp /mysite.template /etc/nginx/conf.d/default.conf 
sed -i "s/__HTTP_HOST__/$(echo "$HTTP_HOST" | tr ',' ' ')/g" /etc/nginx/conf.d/default.conf
sed -i "s/__PATH_DIR__/default/g" /etc/nginx/conf.d/default.conf
ls -lha /etc/nginx/paths
nginx -g 'daemon off;'
