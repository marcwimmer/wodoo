#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x

echo "Applying patches"
cd $SERVER_DIR
dirty=$(git diff --quiet --exit-code && echo 'clean' || echo '')
if [[ "$dirty" != 'clean' ]]; then 
	echo "odoo directory is not clean - cannot reset to apply patches"
	if [[ "$ALLOW_DIRTY_ODOO" == "1" ]]; then
		echo "No patches applied - odoo is dirty - you probably try something in odoo source"
		echo "Variable ALLOW_DIRTY_ODOO is set."
		exit 0
	else
		cd $SERVER_DIR
		git checkout -f
		git clean -xdff
	fi
fi

/opt/odoo/admin/apply_patches.sh || {
    echo "Error at applying patches! Please check output and the odoo version"
    exit -1
}


cd /opt/odoo/admin/module_tools
python <<-EOF
	import module_tools
	module_tools.remove_module_install_notifications("$ACTIVE_CUSTOMS")
EOF

