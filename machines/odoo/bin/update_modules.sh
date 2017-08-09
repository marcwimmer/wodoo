#!/bin/bash
MODULE=$1
set -x
set -e

source /env.sh
/apply-env-to-config.sh
/sync_source.sh

function get_modules() {
	mode=$1 #to_install, to_update
	if [[ -z "$MODULE" ]]; then
		cd /opt/openerp/admin/module_tools
		MODULE=$(python <<-EOF
		import module_tools
		module_tools.get_customs_modules("/opt/openerp/active_customs", "$mode")
		EOF
		)
	fi
	echo $MODULE
}

function delete_qweb() {
    # for odoo delete all qweb views and take the new ones;
	MODULE=$(get_modules $1)
	$(
	cd /opt/openerp/admin/module_tools
	python -c"import module_tools; module_tools.delete_qweb('$MODULE')"
	)
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
	MODULE=$(get_modules $1)
	if [[ -n "$MODULE" ]]; then
		OPERATOR="-u"
		if [[ "$1" == "to_install" ]]; then
			OPERATOR="-i"
		fi
		time sudo -H -u odoo /opt/openerp/versions/server/openerp-server \
			-c /home/odoo/config_openerp \
			-d $DBNAME \
			$OPERATOR $MODULE \
			--stop-after-init \
			--log-level=debug  \
			$TESTS

		echo "$1 $MODULE done"
	fi
}

if [[ "$ODOO_MODULE_UPDATE_DELETE_QWEB" == "1" ]]; then
	delete_qweb 'to_update'
fi
update 'to_install'
update 'to_update'
