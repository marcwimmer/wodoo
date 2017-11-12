#!/bin/bash
function get_modules() {
	local mode
	mode="$1" #to_install, to_update
	cd /opt/odoo/admin/module_tools
	python <<EOF
import module_tools
modules = []
if "$mode" == "to_install":
	modules += module_tools.get_uninstalled_modules_where_otheres_depend_on()
else:
	modules += module_tools.get_customs_modules("/opt/odoo/active_customs", "$mode")
print ','.join(sorted(list(set(modules))))
EOF
}

function get_modules_that_need_to_be_installed_as_depended_on() {
	cd /opt/odoo/admin/module_tools
	python <<-EOF
	import module_tools
	module_tools.get_uninstalled_modules_where_otheres_depend_on()
	EOF
}

function delete_qweb() {
    # for odoo delete all qweb views and take the new ones;
	local __module__
	__module__="$1"
	cd /opt/odoo/admin/module_tools
	python -c"import module_tools; module_tools.delete_qweb('$__module__')"
}

function is_module_installed() {
	if [[ -z "$1" ]]; then
		echo '0'
	else
		local installed
		installed=$(
		cd /opt/odoo/admin/module_tools
		python -c"import module_tools; print '1' if module_tools.is_module_installed('$1') else '0'"
		)
		echo "$installed"
	fi }

function update() {
	local __mode__
	local __module__
	__mode__="$1"
	__module__="$2"

	if [[ -z "$__mode__" || -z "$__module__" ]]; then
		echo "Requires mode and modules"
		exit -1
	fi

	if [[ "$__mode__" != "i" && "$__mode__" != "u" ]]; then
		echo "Requires mode 'i' or 'u'"
		exit -1
	fi

	if [[ "$__module__" == "all" ]]; then
		echo "Update all not allowed"
		exit -1
	fi
	
	if [[ "$ODOO_MODULE_UPDATE_RUN_TESTS" ]]; then
		TESTS='--test-enable'
	else
		TESTS=''
	fi

	echo "$__module__"
	time sudo -H -u "$ODOO_USER" "$SERVER_DIR/openerp-server" \
		-c "$CONFIG_DIR/config_openerp" \
		-d "$DBNAME" \
		-"$__mode__" "$__module__" \
		--stop-after-init \
		--log-level=debug  \
		$TESTS

	echo "$1 $__module__ done"
}

function update_module_list() {
	if [[ "$(is_module_installed "update_module_list")" != "1" ]]; then
		echo "Update Module List is not installed - installing it..."
		update "i" "update_module_list"
	else
		update "u" "update_module_list"
	fi
}

function check_for_dangling_modules() {
	DANGLING="$(
	cd /opt/odoo/admin/module_tools
	python <<-EOF
	import module_tools
	dangling = module_tools.dangling_modules()
	print dangling
	EOF
	)"
}

function main() {
	set -e
	set +x
	[[ "$VERBOSE" == "1" ]] && set -x
	MODULE=$1

	echo "--------------------------------------------------------------------------"
	echo "Updating Module $MODULE"
	echo "--------------------------------------------------------------------------"

	if [[ "$MODULE" == "all" ]]; then
		MODULE=""
	fi

	/apply-env-to-config.sh

	summary=()
	# could be, that a new version is triggered
	check_for_dangling_modules

	if [[ "$DANGLING" == "0" ]]; then
		update_module_list
	fi

	if [[ -z "$MODULE" ]]; then
		MODULE=$(get_modules "to_update")
	fi

	for module in ${MODULE//,/ }; do
		if [[ "$(is_module_installed "$module")" != "1" && -n "$MODULE" ]]; then
			echo "installing $module"
			update 'i' "$module"
			summary+=( "INSTALL $module" )
		fi
	done

	if [[ "$ODOO_MODULE_UPDATE_DELETE_QWEB" == "1" ]]; then
		delete_qweb "$MODULE"
	fi
	update 'u' "$MODULE"

	echo
	echo
	echo "--------------------------------------------------------------------------------"
	echo "Summary of update module"
	echo "--------------------------------------------------------------------------------"
	echo
	for i in "${summary[@]}"; do
		echo "$i"
	done
	echo "UPDATE ${MODULE:0:30}..."
	echo
	echo
	echo
}


main "$1"
