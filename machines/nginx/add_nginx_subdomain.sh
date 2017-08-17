#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x

if [[ -z "$4" ]]; then
	echo "Call add_nginx_subdomain.sh SUBDOMAIN DNSNAME PORT"
	exit -1
fi
SUBDOMAIN=$1
DNSNAME=$2
PORT=$3
SUBDOMAIN_DIR=$4

DOLLAR='$'
tee $SUBDOMAIN_DIR/${DNSNAME}_${SUBDOMAIN/\//}.subdomain <<EOF
location $1 {

	set $DOLLAR${SUBDOMAIN/\//}_${DNSNAME} $DNSNAME;
	resolver 127.0.0.11;
	proxy_pass http://$DOLLAR${SUBDOMAIN/\//}_${DNSNAME}:$PORT;
}

EOF
