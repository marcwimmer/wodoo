#!/bin/bash
set -e
set -x

############################################################################
#                        Pre-Checks
############################################################################
if [[ -z "$CUSTOMS" ]]; then
    echo "CUSTOMS required!"
    exit -1
fi

if [[ -z "$BRANCH" ]]; then
    echo "BRANCH required!"
    exit -1
fi


source /env.sh


/set_permissions.sh

############################################################################
#                        /opt/openerp/admin
############################################################################
# installl initial openerp version source codes
echo "Updating /opt/openerp/admin"

if [ ! -d /opt/openerp/admin ]; then
    cd /opt/openerp
    if [ -d /tmp/admin ]; then
        rm -Rf /tmp/admin
    fi
    git clone /opt/openerp.git/admin /tmp/admin
    /usr/bin/python /tmp/admin/clone_from_local_repos.py --gitlocalsource /opt/openerp.git --customs admin
    rm -Rf /tmp/admin
fi
cd /opt/openerp/admin
git clean -d -x -f
git pull
source /opt/openerp/admin/setup_bash

############################################################################
#                        /opt/openerp/versions
############################################################################
echo "Updating odoo src"
/opt/openerp/admin/switch $CUSTOMS


############################################################################
#                        /opt/openerp/customs/$CUSTOMS
############################################################################
mkdir -p /opt/openerp/customs
chown odoo:odoo /opt/openerp/customs -R

if [[ ! -d /opt/openerp/customs/$CUSTOMS ]]; then
    HOME=/home/odoo /opt/openerp/admin/switch $CUSTOMS $BRANCH || {
        rm -Rf /opt/openerp/customs/$CUSTOMS
        echo "Pulling failed!"
        exit -1
    }
fi
cd /opt/openerp/customs/$CUSTOMS
git checkout $BRANCH -f
git clean -d -x -f
git pull
git submodule update --init --recursive
/opt/openerp/admin/oeln $CUSTOMS


############################################################################
#                        DONE
############################################################################
exit 0
