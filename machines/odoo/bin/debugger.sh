#!/bin/bash

# append configuration option to run old odoo on port 8072
case "$ODOO_VERSION" in
	"7.0" | "6.1" | "6.0")
		echo "xmlrpc_port=8072" >> /home/odoo/config_debug
		;;
esac

set +x
LOCKFILE=$(mktemp -u)
echo "Starting debugger"
echo "Watching File $DEBUGGER_WATCH"
WATCHER=/tmp/watcher.sh  # needed so that due to set_trace debugging is possible from within this script

last_mod=''
last_unit_test=''

# empty file
>| "$DEBUGGER_WATCH"


function odoo_kill() {
	pkill -9 -f /opt/odoo > /dev/null 2>&1
}


cat > $WATCHER <<"EOF"
#!/bin/bash
# This bash scripts kills the odoo process, so that the 
# while is continued 

LOCKFILE=$1

function odoo_kill() {
	pkill -9 -f /opt/odoo > /dev/null 2>&1
}

last_mod=""
while true; do

	new_mod=$(stat -c %y $DEBUGGER_WATCH)

	if [[ "$new_mod" != "$last_mod" ]]; then
		action=$(awk '{split($0, a, ":"); print a[1]}' < "$DEBUGGER_WATCH")


		# actions that no restart require

		if [[ "$action" == 'update_view_in_db' ]]; then
			params=$(awk '{split($0, a, ":"); print a[2]}' < "$DEBUGGER_WATCH")
			filepath=$(echo "$params" | awk '{split($0, a, "|"); print a[1]}')
			lineno=$(echo "$params" | awk '{split($0, a, "|"); print a[2]}')

			cd /opt/odoo/admin/module_tools || exit -1
			python<<-EOF
			import module_tools
			module_tools.update_view_in_db("$filepath", $lineno)
			EOF
		else
			(
			flock -x 200

			odoo_kill

			) 200>$LOCKFILE
		fi

		last_mod=$new_mod
	fi


	sleep 0.1

done
EOF

# start watcher
pkill -9 -f $WATCHER
/bin/bash $WATCHER "$LOCKFILE" &
proc_id_watcher=$!
self=$$

trap "kill -9 $proc_id_watcher; kill -9 $self" SIGINT


while true; do


		new_mod=$(stat -c %y "$DEBUGGER_WATCH")

		if [[ "$new_mod" != "$last_mod" || -z "$last_mod" ]]; then
			sleep 0.2
			(

				flock -x 200
			) 200> $LOCKFILE

			# example content
			# debug
			# unit_test:account_module1

			action=$(awk '{split($0, a, ":"); print a[1]}' < "$DEBUGGER_WATCH")
			odoo_kill

			if [[ -z "$action" ]]; then
				action='debug'
			fi

			if [[ "$action" == 'debug' ]]; then
				reset
				/debug.sh

			elif [[ "$action" == 'quick_restart' ]]; then
				reset
				/debug.sh -quick


			elif [[ "$action" == 'update_module' ]]; then
				module=$(awk '{split($0, a, ":"); print a[2]}' < "$DEBUGGER_WATCH")
				/update_modules.sh "$module" && {
					/debug.sh -quick
				}

			elif [[ "$action" == 'unit_test' ]]; then
				reset
				last_unit_test=$(awk '{split($0, a, ":"); print a[2]}' < "$DEBUGGER_WATCH")
				/unit_test.sh "$last_unit_test"

			elif [[ "$action" == 'last_unit_test' ]]; then
				if [[ -n "$last_unit_test" ]]; then
					/unit_test.sh "$last_unit_test"
				fi

			elif [[ "$action" == 'export_i18n' ]]; then
				# export_i18n:lang:module
				lang=$(awk '{split($0, a, ":"); print a[2]}' < "$DEBUGGER_WATCH")
				module=$(awk '{split($0, a, ":"); print a[3]}' < "$DEBUGGER_WATCH")
				/export_i18n.sh "$lang" "$module"
				
			elif [[ "$action" == 'import_i18n' ]]; then
				# import_i18n:lang:filepath
				lang=$(awk '{split($0, a, ":"); print a[2]}' < "$DEBUGGER_WATCH")
				filepath=$(awk '{split($0, a, ":"); print a[3]}' < "$DEBUGGER_WATCH")
				/import_i18n.sh "$lang" "$filepath"

			fi

			last_mod=$new_mod
		fi

		sleep 0.2

done
