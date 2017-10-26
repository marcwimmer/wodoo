#!/bin/bash
export DIR="$(realpath ../..)"
docker-compose run \
	--name "odoo_bash_$(uuidgen)" \
	-e HOST_ODOO_HOME="$DIR" \
	simplebash bash
