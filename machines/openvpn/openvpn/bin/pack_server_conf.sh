#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x
cd $KEYFOLDERROOT
mkdir server_export
cp $KEYFOLDER/server.crt ./server_export/
cp $KEYFOLDER/server.key ./server_export/server.key
cp $KEYFOLDER/ca.crt ./server_export/ 
cp $KEYFOLDER/ta.key ./server_export/ta.key
cp $KEYFOLDER/dh$KEY_SIZE.pem ./server_export/dh$KEY_SIZE.pem
FILENAME=./server_export/server.conf
cp /root/confs/server.conf $FILENAME

sed -i "s|__CIPHER__|${CIPHER}|g" $FILENAME

cd server_export
tar -czf ../server.tgz ./*
cd ..
mv server.tgz /root/server_out/
rm -rf ./server_export 

