#!/bin/bash
[[ "$VERBOSE" == "1" ]] && set -x
set -e

if [[ -z "$RESTOREFILE" ]]; then
	echo "RESTOREFILE is missing."
	exit -1
fi

/set_permissions.sh
tar vxfz "$RESTOREFILE" -C /
