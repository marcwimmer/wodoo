#!/bin/bash
[[ "$VERBOSE" == "1" ]] && set -x

function DEL() {
	[[ -n "$1" ]] && find $1 -delete 2>/dev/null
}

DEL $KEY_DIR
DEL $PATH_CA
DEL $PATH_CCD
DEL $SERVER_OUT
DEL $CLIENT_OUT

echo "Everything purged"
