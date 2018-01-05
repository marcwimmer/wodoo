#!/bin/bash
# Place a file upstream.path in the root directory of machines
# 
# /calendar http://davical:80/
# 1. parameter: the url you have to enter at the browser, here: http://<host>/calendar
# 2. parameter: upstream
# 3. parameter: output filename
#

set -e
[[ "$VERBOSE" == "1" ]] && set -x

if [[ -z "$3" ]]; then
	echo "Call add_upstream.sh LOCATION UPSTREAM OUTPUTFILENAME"
	exit -1
fi
LOCATION="$1"
UPSTREAM="${2%/}"
OUTPUT_FILENAME="$3"
REWRITE_RULES="$4"
PROXY_NAME=${LOCATION//\//SLASH}
URL_BALANCER_MANAGER="$LOCATION/__balancer_manager__"
URL_BALANCER_MANAGER="${URL_BALANCER_MANAGER//\/\//\/}"

URL_SERVER_STATUS="/__server_status__"

DOLLAR='$'
tee "$OUTPUT_FILENAME" >/dev/null  <<EOF

#https://httpd.apache.org/docs/2.4/howto/reverse_proxy.html

<Proxy balancer://$PROXY_NAME>
	BalancerMember $UPSTREAM hcmethod=GET hcpasses=1 hcfails=1 hcinterval=2 hcuri=/
</Proxy>

<Location $URL_SERVER_STATUS>
    SetHandler server-status
    Require all granted
</Location>

<Location ${URL_BALANCER_MANAGER}>
    SetHandler balancer-manager
	Require all granted
</Location>

ProxyPass $URL_BALANCER_MANAGER !
ProxyPass $URL_SERVER_STATUS !
ProxyPass $LOCATION balancer://$PROXY_NAME/
ProxyPassReverse $LOCATION balancer://$PROXY_NAME/

$REWRITE_RULES

EOF
