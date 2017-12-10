#!/bin/bash
DIR="$(realpath ../..)"
export DIR="$DIR"
uuid="$(uuidgen)"
HOSTNAME_TO_USE="host_${uuid}"
export HOSTNAME_TO_USE="$HOSTNAME_TO_USE"

if [[ -n "$DISPLAY" ]]; then
	xhost +local:"$HOSTNAME_TO_USE"
fi
docker-compose run \
	--name "odoo_bash_$uuid" \
	-e HOST_ODOO_HOME="$DIR" \
	-e UID="$UID" \
	-e USER="$USER" \
	simplebash bash
