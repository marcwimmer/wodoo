#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x

ACTIVE_CUSTOMS=/opt/odoo/active_customs

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

mkdir -p /opt/odoo
echo "rsyncing odoo source"
rsync /opt/src/admin/ /opt/odoo/admin/ -ar

source /env.sh
source /opt/odoo/admin/setup_bash

# Setting up productive odoo
echo
echo '------------------------------------------------------------'
echo "Customs: $CUSTOMS"
echo "Version: $ODOO_VERSION"

echo "Syncing odoo to executable dir"
time rsync /opt/src/customs/$CUSTOMS/ $ACTIVE_CUSTOMS/ --info=progress2  -ar --delete --exclude=.git
mkdir -p /opt/odoo/customs
cd /opt/odoo/customs && {
    rm * || true
    ln -s $ACTIVE_CUSTOMS $CUSTOMS
}
chmod a+x /opt/odoo/admin/*.sh

rm -Rf /opt/odoo/server || true
# must be rsync, so that patches apply
ln -s $ACTIVE_CUSTOMS/odoo /opt/odoo/server

/opt/odoo/admin/link_modules $CUSTOMS

echo "Applying patches"
CUSTOMS_DIR=$ACTIVE_CUSTOMS SERVER_DIR=/opt/odoo/server /bin/bash /opt/odoo/admin/apply_patches.sh || {
    echo "Error at applying patches! Please check output and the odoo version"
    exit -1
}

/set_permissions.sh

cd /opt/odoo/admin/module_tools
$(python <<-EOF
import module_tools
module_tools.remove_module_install_notifications("$ACTIVE_CUSTOMS")
EOF
)
