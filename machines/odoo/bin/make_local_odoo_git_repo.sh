#!/bin/bash

if [[ -f "$SERVER_DIR/.git" || ! -d "$SERVER_DIR/.git" ]]; then
	echo "Odoo has no own git repository - creating local git repo in odoo"
	cd "$SERVER_DIR" || exit -1
	git init .
	echo "Cleaning pyc files"
	find -name '*.pyc' -delete
	git add -N .
	git config --global user.email 'odoo'
	git commit -am 'first checkin'
fi

