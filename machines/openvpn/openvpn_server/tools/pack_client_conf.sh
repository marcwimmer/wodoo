#!/bin/bash
set -e
set -x

if [[ -z "$REMOTE" ]]; then
    echo "Please set env \$REMOTE and \$REMOTE_PORT"
    exit -1
fi

cd /root/openvpn-ca

if [[ -z "$1" || -z "$2" || -z "$3" || -z "$4" ]] 
then
    echo "Usage: pack_client_conf.sh keyname configuration-filename tar|notar <finalname>"
    exit -1;
fi

CONF="/root/confs/$2"
FILENAME="./openvpn/$(basename $CONF)"
CLIENT_KEY=$KEYFOLDER/$1.key
CLIENT_CERT=$KEYFOLDER/$1.crt
CA_CERT=$KEYFOLDER/ca.crt
TLS_KEY=$KEYFOLDER/ta.key

mkdir openvpn  
cp $CONF ./openvpn
sed -i "s|__REMOTE__|${REMOTE}|g" $FILENAME
sed -i "s|__REMOTE_PORT__|${REMOTE_PORT}|g" $FILENAME
sed -i "s|__REMOTE_INTERNAL__|${REMOTE_INTERNAL}|g" $FILENAME
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

if [[ "$3" == "tar" ]]; then
    cd openvpn
    tar -cf ../$4 *
    cd ..
    mv $4 /root/client_out/
else
    mv $FILENAME /root/client_out/$4
fi

rm -rf openvpn 
