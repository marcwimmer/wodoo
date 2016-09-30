#!/bin/bash
DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
projectname=$(basename $DIR)
filepath=/lib/systemd/system/${projectname}.service
cp odoo.service $filepath
sed -i "s|__PWD__|${DIR}|g" $filepath
systemctl enable $projectname 
