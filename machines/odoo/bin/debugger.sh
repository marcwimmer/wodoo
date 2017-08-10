#!/bin/bash
set +x

echo "Starting debugger"
echo "Watching File $DEBUGGER_WATCH"

last_mod=''
last_unit_test=''

function kill() {
	PID=$(cat $DEBUGGER_ODOO_PID)
	kill $PID
}
# empty file
>| $DEBUGGER_WATCH

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
			/debug.sh &

		elif [[ "$action" == 'update_module' ]]; then
			module=$(cat $DEBUGGER_WATCH | awk '{split($0, a, ":"); print a[2]}')
			/update_modules.sh $module && {
				/debug.sh -quick &
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
