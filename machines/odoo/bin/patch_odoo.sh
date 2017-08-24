#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x

echo "Applying patches"
cd $SERVER_DIR
git checkout -f
git clean -xdff
/opt/odoo/admin/apply_patches.sh || {
    echo "Error at applying patches! Please check output and the odoo version"
    exit -1
}


cd /opt/odoo/admin/module_tools
python <<-EOF
	import module_tools
	module_tools.remove_module_install_notifications("$ACTIVE_CUSTOMS")
EOF

