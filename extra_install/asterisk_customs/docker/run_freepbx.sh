#!/bin/bash

if [[ -z "$1" ]]; then
	echo "Please provide the external ip (how this freepbx box is called from phones"
	exit -1
fi

export EXTERNIP="$1"

docker-compose kill freepbx
docker-compose rm -f freepbx
docker-compose build freepbx
docker-compose up -d freepbx

echo "Now goto http://localhost:9080 and setup username password."
echo "Please create PJSIP extensions, not SIP"
echo "Using hostname $EXTERNIP"
