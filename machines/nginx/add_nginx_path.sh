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
DOMAIN=$6  # default; otherwise name from odoo_instances

if [[ -z "$DOMAIN" ]]; then
	DOMAIN=default
fi
if [[ -z "$OUTPUT_FILENAME" ]]; then
	OUTPUT_FILENAME=$URLPATH_DIR/$DOMAIN/${DNSNAME}_${URLPATH/\//}
else
	OUTPUT_FILENAME="$URLPATH_DIR/$DOMAIN/$OUTPUT_FILENAME"
fi

mkdir -p "$(dirname "$OUTPUT_FILENAME")"

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
	#resolver 127.0.0.11;
	#https://serverfault.com/questions/240476/how-to-force-nginx-to-resolve-dns-of-a-dynamic-hostname-everytime-when-doing-p
	resolver 127.0.0.11 valid=15s;
	proxy_pass http://$DOLLAR${DNSNAME}_${URLPATH/\//}:$PORT;
}

EOF
