#!/bin/bash
set -e
/root/tools/init.sh

if [[ -z "$1" ]]; then
    echo 'name required'
    exit -1
fi

cd $KEYFOLDERROOT

echo "Build Key"
export EASY_RSA="`pwd`"
export KEY_NAME=$1
export OPENSSL="openssl"
export PKCS11TOOL="pkcs11-tool"
export GREP="grep"
export KEY_CONFIG=`$EASY_RSA/whichopensslcnf $EASY_RSA`
export KEY_DIR="$EASY_RSA/keys"
export KEY_CN=$1  # to match CCD

#BUG IN UBUNTU 14.04 and 16.04 PKITOOL:
#http://stackoverflow.com/questions/24255205/error-loading-extension-section-usr-cert/26078472#26078472
sed -i 's|KEY_ALTNAMES="$KEY_CN"|KEY_ALTNAMES="DNS:${KEY_CN}"|g' /usr/share/easy-rsa/pkitool

./build-key --batch $1
