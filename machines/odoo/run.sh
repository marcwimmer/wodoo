#!/bin/bash
set -e
set +x

# Setting up productive odoo
echo Setting up odoo for customs $CUSTOMS

if [[ -z "$CUSTOMS" ]]; then
    echo "CUSTOMS required!"
    exit -1
fi

# installl initial openerp version source codes
if [[ -n "$DO_INIT" || -n "$DO_UPDATE" ]]; then
    echo "Initialising odoo...$DO_INIT_$DO_UPDATE"
    rm -Rf /opt/openerp/* -Rf || true
    if [ ! -d /opt/openerp/admin ]; then
        cd /opt/openerp
        if [ -d /tmp/admin ]; then
            rm -Rf /tmp/admin
        fi
        git clone /opt/openerp.git/admin /tmp/admin
        /usr/bin/python /tmp/admin/clone_from_local_repos.py --gitlocalsource /opt/openerp.git --customs admin
        rm -Rf /tmp/admin
    fi
else
    cd /opt/openerp/admin
    git clean -f
    git pull
fi

source /opt/openerp/admin/setup_bash

if [[ -n "$DO_INIT" || -n "$DO_UPDATE" ]]; then
    echo "Switching to $CUSTOMS"
    HOME=/home/odoo /opt/openerp/admin/switch $CUSTOMS
    if [[ ! -d /opt/openerp/customs/$CUSTOMS ]]; then
        ls -lha /opt/openerp/customs
        echo Customs failed to checkout
        exit -1
    fi
    if [[ -d /home/odoo/.local/share/Odoo ]]; then
        rm -Rf /home/odoo/.local/share/Odoo/*
    fi
fi
chown odoo:odoo /opt/openerp/ -R
chown odoo:odoo /home/odoo/.local -R

if [[ -n "$DO_INIT" || -n "$DO_UPDATE" ]]; then
    cd /opt/openerp/customs/$CUSTOMS
    echo "Trying to checkout deploy branch"
    git checkout deploy -f
    git submodule update --init --recursive
    /opt/openerp/admin/oeln $CUSTOMS
    cat /opt/openerp/versions/.version
fi

ODOO_VERSION=$(cat /opt/openerp/customs/$CUSTOMS/.version)
echo "Odoo version is $ODOO_VERSION"

# install requirements
if [[ -n "$DO_INIT" ]]; then
    echo "Installing requirements from odoo"
    wget https://raw.githubusercontent.com/odoo/odoo/$ODOO_VERSION/requirements.txt -O /root/requirements_odoo.txt
    pip install -r /root/requirements_odoo.txt
fi


if [[ -n "$DO_UPDATE" ]]; then
    sudo -H -u odoo /opt/openerp/versions/server/openerp-server -d $DBNAME -u all --stop-after-init --log-level=debug || echo 'odoo update executed'
    echo "Update of odoo done"
    exit 0
fi

if [[ -n "$DO_INIT" ]]; then
    echo "Init of odoo done"
    exit 0
fi

echo "Starting up odoo"
START_LINE="sudo -H -u odoo /opt/openerp/versions/server/openerp-server -d $DBNAME --log-level=debug"
eval $START_LINE

while true;
do
    echo heartbeat

    if [[ -f /tmp/stop ]]; then
        pkill -9 -f openerp-server || true
        rm /tmp/stop
    fi

    if [[ -f /tmp/start ]]; then
        rm /tmp/start
        eval $START_LINE &
    fi


    sleep 1

done
