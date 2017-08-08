#!/bin/bash
MODULE=$1
set +x
source /env.sh
/sync_source.sh

if [[ -n "$MODULE" ]]; then
    echo "updating just $MODULE"
else
    echo "Getting list of custom modules"
    MODULE=$(/opt/openerp/admin/update_custom_modules.py $CUSTOMS)
fi

function delete_qweb() {
    # for odoo delete all qweb views and take the new ones;
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
	time sudo -H -u odoo /opt/openerp/versions/server/openerp-server \
		-c /home/odoo/config_openerp \
		-d $DBNAME \
		-u $MODULE \
		--stop-after-init \
		--log-level=debug  \
		$TESTS

	echo "Updated $MODULE"
}

if [[ "$ODOO_MODULE_UPDATE_DELETE_QWEB" == "1" ]]; then
	delete_qweb
fi
update
