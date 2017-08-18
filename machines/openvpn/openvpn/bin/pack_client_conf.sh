#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x
check_has_ca.sh

if [[ -z "$OVPN_REMOTE" || -z "$OVPN_REMOTE_PORT" ]]; then
    echo "Please set env \$OVPN_REMOTE and \$OVPN_REMOTE_PORT"
    exit -1
fi

prepare_ca_tools.sh
cd $EASY_RSA

if [[ -z "$1" || -z "$2" || -z "$3" ]] 
then
    echo "Usage: pack_client_conf.sh keyname configuration-filename <finalname> -tar"
    exit -1;
fi

KEYNAME=$1
TEMPLATENAME=$2
FINALNAME=$3

if [[ -z "$OVPN_REMOTE" || -z "$OVPN_REMOTE_PORT" || -z "$OVPN_CIPHER" ]]; then
	echo "Missing OVPN_REMOTE, OVPN_PORT or OVPN_CIPHER"
	exit -1
fi

TMP=$(mktemp -u)
mkdir -p $TMP
CONF="$PATH_CONFIG_TEMPLATES/$TEMPLATENAME"
FILENAME="$TMP/$(basename $CONF)"
CLIENT_KEY=$KEY_DIR/$KEYNAME.key
CLIENT_CERT=$KEY_DIR/$KEYNAME.crt
CA_CERT=$KEY_DIR/ca.crt
TLS_KEY=$KEY_DIR/ta.key
if [[ ! -d ./openvpn ]]
then
	mkdir openvpn
fi

#mkdir openvpn  
cp $CONF $TMP
sed -i "s|__REMOTE__|${OVPN_REMOTE}|g" $FILENAME
sed -i "s|__REMOTE_PORT__|${OVPN_REMOTE_PORT}|g" $FILENAME
sed -i "s|__INTERNAL_REMOTE__|${OVPN_INTERNAL_REMOTE}|g" $FILENAME
sed -i "s|__INTERNAL_REMOTE_PORT__|${OVPN_INTERNAL_REMOTE_PORT}|g" $FILENAME
sed -i "s|__CIPHER__|${OVPN_CIPHER}|g" $FILENAME

echo "<key>" >> $FILENAME
cat $CLIENT_KEY >> $FILENAME
echo "</key>">> $FILENAME
echo "<cert>">> $FILENAME
cat $CLIENT_CERT >> $FILENAME
echo "</cert>">>$FILENAME
echo "<ca>" >>$FILENAME
cat $CA_CERT >> $FILENAME
echo "</ca>" >> $FILENAME
echo "<tls-auth>" >> $FILENAME
cat $TLS_KEY  >> $FILENAME
echo "</tls-auth>">>$FILENAME

echo "$*" |grep -q '[-]tar' && {
    cd $TMP
    tar -cf ../$FINALNAME *
    cd ..
    mv $FINALNAME /root/client_out/
} || {
    mv $FILENAME /root/client_out/$FINALNAME
}

rm -Rf $TMP
