#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x
check_has_ca.sh

if [[ -z "$1" ]]; then
    echo 'name required'
    exit -1
fi

if [[ $(find $KEY_DIR -name $1.key) ]]; then
	echo "$*" |grep -q '[-]abort-on-existing' && {
		exit 0
	}
	echo "$*" |grep -q '[-]silent' || {
		echo "Client key $1 already created - aborting."
		exit -1
	}
fi

prepare_ca_tools.sh
cd $EASY_RSA

echo "Build Key"
export KEY_CONFIG=`$EASY_RSA/whichopensslcnf $EASY_RSA`
export KEY_CN=$1  # to match CCD
export KEY_NAME="client-${OVPN_DOMAIN}-$1"
prepare_ca_tools.sh

#BUG IN UBUNTU 14.04 and 16.04 PKITOOL:
#http://stackoverflow.com/questions/24255205/error-loading-extension-section-usr-cert/26078472#26078472
#sed -i 's|KEY_ALTNAMES="$KEY_CN"|KEY_ALTNAMES="DNS:${KEY_CN}"|g' /usr/share/easy-rsa/pkitool
perl -p -i -e 's|^(subjectAltName=)|#$1|;' $KEY_CONFIG

./build-key --batch $1
