#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x

if [[ -z "$4" ]]; then
	echo "Call add_nginx_path.sh PATH DNSNAME PORT"
	exit -1
fi
URLPATH=$1
DNSNAME=$2
PORT=$3
URLPATH_DIR=$4
OUTPUT_FILENAME=$5
if [[ -z "$OUTPUT_FILENAME" ]]; then
	OUTPUT_FILENAME=$URLPATH_DIR/${DNSNAME}_${URLPATH/\//}
else
	OUTPUT_FILENAME="$URLPATH_DIR/$OUTPUT_FILENAME"
fi

DOLLAR='$'

if [[ "$1" == "/" ]]; then
	LOCATION="$1" # e.g. /
else
	LOCATION=" = $1"  # e.g. = /cal
fi

tee "$OUTPUT_FILENAME.path" >/dev/null  <<EOF
location $LOCATION
{
	set $DOLLAR${DNSNAME}_${URLPATH/\//} $DNSNAME;
	resolver 127.0.0.11;
	proxy_pass http://$DOLLAR${DNSNAME}_${URLPATH/\//}:$PORT;
}

EOF
