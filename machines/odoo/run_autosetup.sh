#!/bin/bash
# Autosetup searches in /opt/openerp/customs/$CUSTOMS/autosetup for 
# *.sh files; makes them executable and executes them
# You can do setup there, like deploying ssh keys and so on
set -e

cd /opt/openerp/customs/$CUSTOMS
if [[ ! -d autosetup ]]; then
    exit 0
fi
cd autosetup

for file in *.sh; do
    chmod a+x $file
    echo "executing $file"
    eval "./$file"
done
