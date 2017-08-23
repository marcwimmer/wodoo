#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x
MODULE=$1

echo "--------------------------------------------------------------------------"
echo "Updating Module $MODULE"
echo "--------------------------------------------------------------------------"

if [[ "$MODULE" == "all" ]]; then
	MODULE=""
fi

source /env.sh
/apply-env-to-config.sh
/sync_source.sh

function get_modules() {
	mode=$1 #to_install, to_update
	if [[ -z "$MODULE" ]]; then
		cd /opt/odoo/admin/module_tools
		echo "$(python <<-EOF
		import module_tools
		module_tools.get_customs_modules("/opt/odoo/active_customs", "$mode")
		EOF
		)"
	else
		echo $MODULE
	fi
}

function delete_qweb() {
    # for odoo delete all qweb views and take the new ones;
	local __module__=$(get_modules $1)
	$(
	cd /opt/odoo/admin/module_tools
	python -c"import module_tools; module_tools.delete_qweb('$__module__')"
	)
}

function is_module_installed() {
	if [[ -z "$MODULE" ]]; then
		echo '0'
	else
		installed=$(
		cd /opt/odoo/admin/module_tools
		python -c"import module_tools; print '1' if module_tools.is_module_installed('$MODULE') else '0'"
		)
		echo $installed
	fi
}

function update() {
	if [[ "$ODOO_MODULE_UPDATE_RUN_TESTS" ]]; then
		TESTS='--test-enable'
	else
		TESTS=''
	fi
	echo
	echo "Updating modules $MODULE..."
	echo
	local __module__=$(get_modules $1)
	if [[ -n "$__module__" ]]; then
		OPERATOR="-u"
		if [[ "$1" == "to_install" ]]; then
			OPERATOR="-i"
			time sudo -H -u odoo /opt/odoo/server/openerp-server \
				-c /home/odoo/config_openerp \
				-d $DBNAME \
				-u update_module_list \
				--stop-after-init \
				--log-level=error 
			fi
		echo "$__module__"
		time sudo -H -u odoo /opt/odoo/server/openerp-server \
			-c /home/odoo/config_openerp \
			-d $DBNAME \
			$OPERATOR $__module__ \
			--stop-after-init \
			--log-level=debug  \
			$TESTS

		echo "$1 $__module__ done"
	fi
}

if [[ "$ODOO_MODULE_UPDATE_DELETE_QWEB" == "1" ]]; then
	delete_qweb 'to_update'
fi

if [[ "$(is_module_installed)" != "1" && -n "$MODULE" ]]; then
	update 'to_install'
fi
update 'to_update'
