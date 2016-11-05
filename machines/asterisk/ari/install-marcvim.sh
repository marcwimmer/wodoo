#!/bin/bash
apt-get install -y wget libruby
cd /tmp
wget http://vim.itewimmer.de/marcvim_installer_ubuntu-16.04.sh
/bin/bash marcvim_installer_ubuntu-16.04.sh

cp /usr/local/bin/vim/ /usr/bin
