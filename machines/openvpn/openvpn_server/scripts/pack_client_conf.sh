#!/bin/bash
set -e

cd /root/openvpn-ca

if [ -z "$1" ] 
then
    echo "Usage: $0 client";
    exit; 
fi

if [[ "asterisk" == "$1" ]]
then
    CONF=/root/confs/asterisk.conf;
elif [[ "CLIENT" == "$1" ]]
then
    CONF=/root/confs/vpn.cnf;
else
    echo "invalid: $1"
    exit -1
fi

FILENAME="./openvpn/$(basename $CONF)"
CLIENT_KEY=$KEYFOLDER/$1.key
CLIENT_CERT=$KEYFOLDER/$1.crt
CA_CERT=$KEYFOLDER/ca.crt
TLS_KEY=$KEYFOLDER/ta.key

mkdir openvpn  
cp $CONF ./openvpn
sed -i "s|__REMOTE__|${REMOTE}|g" $FILENAME
sed -i "s|__REMOTE_PORT__|${REMOTE_PORT}|g" $FILENAME

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

cd openvpn
tar -cf ../$1.tar *
cd ../
mv $1.tar /root/client_out/
rm -rf ./openvpn 
