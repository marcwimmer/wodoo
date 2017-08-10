#!/bin/bash
set +x

echo "Starting debugger"
echo "Watching File $DEBUGGER_WATCH"
WATCHER=/tmp/watcher.sh  # needed so that due to set_trace debugging is possible from within this script

last_mod=''
last_unit_test=''

function kill() {
	PID=$(cat $DEBUGGER_ODOO_PID)
	kill $PID
}
# empty file
>| $DEBUGGER_WATCH

cat > $WATCHER <<"EOF"
#!/bin/bash
# This bash scripts kills the odoo process, so that the 
# while is continued 
last_mod=""
while true; do

	new_mod=$(stat -c %y $DEBUGGER_WATCH)

	if [[ "$new_mod" != "$last_mod" ]]; then

		pkill -9 -f /opt/openerp
		last_mod=$new_mod
	fi

	sleep 0.5

done
EOF

# start watcher
pkill -9 -f $WATCHER
chmod a+x $WATCHER
$WATCHER &

while true; do

	new_mod=$(stat -c %y $DEBUGGER_WATCH)

	if [[ "$new_mod" != "$last_mod" || -z "$last_mod" ]]; then

		# example content
		# debug
		# unit_test:account_module1

		action=$(cat $DEBUGGER_WATCH | awk '{split($0, a, ":"); print a[1]}')

		if [[ -z "$action" ]]; then
			action='debug'
		fi

		if [[ "$action" == 'debug' ]]; then
			reset
			/debug.sh

		elif [[ "$action" == 'update_module' ]]; then
			module=$(cat $DEBUGGER_WATCH | awk '{split($0, a, ":"); print a[2]}')
			/update_modules.sh $module && {
				/debug.sh -quick
			}

		elif [[ "$action" == 'unit_test' ]]; then
			reset
			last_unit_test=$(cat $DEBUGGER_WATCH | awk '{split($0, a, ":"); print a[2]}')
			/unit_test.sh $last_unit_test

		elif [[ "$action" == 'last_unit_test' ]]; then
			if [[ -n "$last_unit_test" ]]; then
				/unit_test.sh $last_unit_test
			fi

		fi
		last_mod=$new_mod
	fi

	sleep 0.5

done

pkill -9 -f $WATCHER
