#!/bin/bash
set -e
set -x


git config --global user.name $GIT_USER_NAME
git config --global user.email $GIT_USER_EMAIL

if [[ -n "$RESTORE_FILES" ]]; then
    while true;
    do
        # command is executed via manage.sh docker exec; wait here until killed
        sleep 1
    done
fi

# Setting up productive odoo
echo Setting up odoo for customs $CUSTOMS

if [[ -z "$CUSTOMS" ]]; then
    echo "CUSTOMS required!"
    exit -1
fi

if [[ -n "$DO_INIT" ]]; then
    echo "setting ownership of /opt/oefiles to odoo"
    chown odoo:odoo /opt/oefiles -R
fi

if [[ -n "$DO_BACKUP" ]]; then
    echo 'Tarring /opt/oefiles'
    tar cf /opt/dumps/oefiles.tar /opt/oefiles
    exit 0
fi

if [[ -n "$DO_INIT" || -n "$DO_UPDATE" ]]; then
    echo "installing required minimum pip packages"
    pip install --upgrade pip
    pip install requests[security]
    pip install glob2
    pip install gitpython
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

mkdir -p /opt/openerp/customs
chown odoo:odoo /opt/openerp/ -R

if [[ -n "$DO_INIT" || -n "$DO_UPDATE" ]]; then

    if [[ -z "$DO_QUICK" ]]; then
        while true;
        do
            rm -Rf /opt/openerp/customs/$CUSTOMS || true
            HOME=/home/odoo /opt/openerp/admin/switch $CUSTOMS $BRANCH && break
            echo "Pulling failed - retrying until works"
        done
        cd /opt/openerp/customs/$CUSTOMS
        rm * -Rf
        git checkout $BRANCH -f
    fi
    git submodule update --init --recursive
    /opt/openerp/admin/oeln $CUSTOMS
fi

ODOO_VERSION=$(cat /opt/openerp/customs/$CUSTOMS/.version)
echo "Odoo version is $ODOO_VERSION"

# use virtualenv installed packages for odoo

echo "Storing server rc file"
cp /home/odoo/.openerp_serverrc /opt/permanent/.openerp_serverrc

if [[ -n "$DO_INIT" ]]; then
    echo 'init done'
    exit 0
fi

if [[ -n "$DO_UPDATE" ]]; then

    if [[ -z "$DO_QUICK" ]]; then
        sudo -H -u odoo /opt/openerp/versions/server/openerp-server \
            -d $DBNAME \
            -u $UPDATE_MODULE \
            --stop-after-init \
            --log-level=debug || echo 'odoo update executed'
        echo "Update of odoo done"
        exit 0
    fi
fi

# NORMAL STARTUP - start odo here

# RUN Scripts from autosetup
echo "Executing autosetup..."
/run_autosetup.sh $ODOO_PROD
echo "Done autosetup"

echo "Recreating server rc file"
cp /opt/permanent/.openerp_serverrc /home/odoo/.openerp_serverrc 
chown odoo:odoo /home/odoo/.openerp_serverrc 

echo on version 6.1 start soffice
if [[ "$ODOO_VERSION" == "6.1" ]]; then
    sudo -H -u odoo /usr/bin/soffice --nologo --nofirststartwizard --headless --norestore --invisible --accept="socket,host=localhostort=8100,tcpNoDelay=1;urp;" &

fi

echo "Starting up odoo"
#sudo -H -u odoo /opt/openerp/versions/server/openerp-server -c /home/odoo/config_openerp -d $DBNAME --log-level=debug &
sudo -H -u odoo /opt/openerp/versions/server/openerp-gevent -c /home/odoo/config_gevent  -d $DBNAME --log-level=debug &
sleep 3

set +x
while true;
do
    if [[ -f /tmp/stop ]]; then
        pkill -9 -f openerp-server || true
        rm /tmp/stop
    fi

    if [[ -f /tmp/start ]]; then
        rm /tmp/start
        eval $START_LINE &
    fi

    pgrep -f openerp > /dev/null || {
        [[ -f /tmp/debugging ]] || {
            echo 'exiting - no odoo here...'
            exit -1
        }
    }

    sleep 1

done
