#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x

echo "Applying patches"
cd "$SERVER_DIR" || exit -1

/make_local_odoo_git_repo.sh

dirty=$(git diff --quiet --exit-code && echo 'clean' || echo '')
if [[ "$dirty" != 'clean' ]]; then 
	echo "odoo directory is not clean - cannot reset to apply patches"
	if [[ "$ALLOW_DIRTY_ODOO" == "1" ]]; then
		echo "No patches applied - odoo is dirty - you probably try something in odoo source"
		echo "Variable ALLOW_DIRTY_ODOO is set."
		echo 
		echo "I am going to try to apply existing patches"
	else
		cd "$SERVER_DIR"
		git checkout -f
		git clean -xdff
	fi
fi

/opt/odoo/admin/apply_patches.sh || {
	if [[ "$ALLOW_DIRTY_ODOO" != "1" ]]; then
		echo "Error at applying patches! Please check output and the odoo version"
		exit -1
	fi
}


cd /opt/odoo/admin/module_tools
python <<-EOF
	import module_tools
	module_tools.remove_module_install_notifications("$ACTIVE_CUSTOMS")
EOF

