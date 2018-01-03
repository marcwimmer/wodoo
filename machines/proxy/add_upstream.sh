#!/bin/bash
#
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
UPSTREAM="$2"
OUTPUT_FILENAME="$3"
PROXY_NAME=${LOCATION//\//SLASH}

DOLLAR='$'
tee "$OUTPUT_FILENAME" >/dev/null  <<EOF

<Proxy balancer://$PROXY_NAME/>
	BalancerMember $UPSTREAM
</Proxy>

<Location $LOCATION>

ProxyPass balancer://$PROXY_NAME/
ProxyPassReverse balancer://$PROXY_NAME/
</Location>
EOF
