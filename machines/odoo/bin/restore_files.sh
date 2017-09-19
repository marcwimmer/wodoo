#!/bin/bash
[[ "$VERBOSE" == "1" ]] && set -x
set -e

/set_permissions.sh
tar vxfz "/opt/dumps/$1" -C /
