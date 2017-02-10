#!/bin/bash
set -e
set -x

cd /opt/src

# always updating
rm /opt/src/* -Rf || true
git clone --branch deploy git.mt-software.de:/git/openerp/modules/asterisk_ari
echo 'done updating ari'

exit 0
