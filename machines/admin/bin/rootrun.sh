#!/bin/bash

if [[ "$ADMINDEBUG" == "1" ]]; then
	/init_odoo.sh

	echo "Entering endless loop now; you can attach and run /run.sh to start debugging"

	while true;
	do
		sleep 1
	done

else

	/init_odoo.sh
	/run.sh
fi
