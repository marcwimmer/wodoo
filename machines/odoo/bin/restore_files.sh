#!/bin/bash
[[ "$VERBOSE" == "1" ]] && set -x
set -e

if [[ -z "$1" ]]; then
	echo "File is missing."
	exit -1
fi

/set_permissions.sh
tar vxfz "/opt/dumps/$1" -C /
