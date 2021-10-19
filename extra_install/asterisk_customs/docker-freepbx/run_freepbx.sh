#!/bin/bash

if [[ -z "$1" ]]; then
	echo "Please provide the external ip (how this freepbx box is called from phones"
	exit -1
fi

export EXTERNIP="$1"

echo "After started goto http://localhost:9080 and setup username password."
echo "Please create PJSIP extensions, not SIP"
echo "Using hostname $EXTERNIP"
echo "Now you should start ./debug_connector_mqtt_asterisk and debug the application"
docker-compose up freepbx

