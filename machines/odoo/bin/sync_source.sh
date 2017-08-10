#!/bin/bash
set -e
set +x

ACTIVE_CUSTOMS=/opt/openerp/active_customs

# optional parameter: the local complete filepath

if [[ -z "$CUSTOMS" ]]; then
    echo "CUSTOMS required!"
    exit -1
fi

if [[ -n "$1" ]]; then
    # sync just one file
    local_path=$(
python - << EOF
path = "$1"
customs = "$CUSTOMS"
path = path.split("customs/{}".format(customs))[1]
print path
EOF
)
    time rsync /opt/src/customs/$CUSTOMS/$local_path $ACTIVE_CUSTOMS/$local_path --info=progress2  -arP --delete --exclude=.git
    exit 0
fi

mkdir -p /opt/openerp
echo "rsyncing odoo source"
rsync /opt/src/admin/ /opt/openerp/admin/ -ar

source /env.sh
source /opt/openerp/admin/setup_bash

# Setting up productive odoo
echo
echo '------------------------------------------------------------'
echo "Customs: $CUSTOMS"
echo "Version: $ODOO_VERSION"

echo "Syncing odoo to executable dir"
time rsync /opt/src/customs/$CUSTOMS/ $ACTIVE_CUSTOMS/ --info=progress2  -ar --delete --exclude=.git
mkdir -p /opt/openerp/versions
mkdir -p /opt/openerp/customs
cd /opt/openerp/customs && {
    rm * || true
    ln -s $ACTIVE_CUSTOMS $CUSTOMS
}
chmod a+x /opt/openerp/admin/*.sh

rm -Rf /opt/openerp/versions || true
mkdir -p /opt/openerp/versions
# must be rsync, so that patches apply
ln -s $ACTIVE_CUSTOMS/odoo /opt/openerp/versions/server

echo "oeln"
/opt/openerp/admin/oeln $CUSTOMS

echo "Applying patches"
CUSTOMS=$CUSTOMS VERSION=$ODOO_VERSION CUSTOMS_DIR=$ACTIVE_CUSTOMS SERVER_DIR=/opt/openerp/versions/server /bin/bash /opt/openerp/admin/apply_patches.sh || {
    echo "Error at applying patches! Please check output and the odoo version"
    exit -1
}

/set_permissions.sh

cd /opt/openerp/admin/module_tools
$(python <<-EOF
import module_tools
module_tools.remove_module_install_notifications("$ACTIVE_CUSTOMS")
EOF
)
