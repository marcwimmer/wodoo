#!/bin/bash

# collect provided vsix files
rsync -v /home/vsix_files --include=*.vsix /home/theia/plugins

pip3 install -r /opt/odoo/requirements.txt


node \
	/home/theia/src-gen/backend/main.js \
	/home/project \
	--hostname=0.0.0.0
