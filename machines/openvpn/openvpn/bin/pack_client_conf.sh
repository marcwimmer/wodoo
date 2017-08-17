#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x
check_has_ca.sh

if [[ -z "$OVPN_REMOTE" || -z "$OVPN_REMOTE_PORT" ]]; then
    echo "Please set env \$OVPN_REMOTE and \$OVPN_REMOTE_PORT"
    exit -1
fi

cd $KEYFOLDER_ROOT

if [[ -z "$1" || -z "$2" || -z "$3" || -z "$4" ]] 
then
    echo "Usage: pack_client_conf.sh keyname configuration-filename <finalname> -tar"
    exit -1;
fi

CONF="/root/confs/$2"
FILENAME="./openvpn/$(basename $CONF)"
CLIENT_KEY=$KEYFOLDER/$1.key
CLIENT_CERT=$KEYFOLDER/$1.crt
CA_CERT=$KEYFOLDER/ca.crt
TLS_KEY=$KEYFOLDER/ta.key
if [[ ! -d ./openvpn ]]
then
	mkdir openvpn
fi
#mkdir openvpn  
cp $CONF ./openvpn
sed -i "s|__REMOTE__|${OVPN_REMOTE}|g" $FILENAME
sed -i "s|__REMOTE_PORT__|${OVPN_REMOTE_PORT}|g" $FILENAME
sed -i "s|__CIPHER__|${CIPHER}|g" $FILENAME

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
    cd openvpn
    tar -cf ../$4 *
    cd ..
    mv $4 /root/client_out/
} || {
    mv $FILENAME /root/client_out/$4
}

rm -rf openvpn 
