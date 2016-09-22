#!/bin/bash
set -e

/usr/sbin/nginx
cd /opt
[ ! -d asterisk_ari ] && {
    git clone git.mt-software.de:/git/openerp/modules/asterisk_ari
}

cd asterisk_ari
git checkout -f deploy
git pull

git config --system user.name $GIT_USER_NAME
git config --system user.email $GIT_USER_EMAIL
git config --system push.default simple

/install/marcvim/marcvim_installer.sh && ~/.vim/bundle/YouCompleteMe/installer.py & 


echo "Simple start stasis by calling /stasis !"
echo 'starting endless loop now; to debug here, please do:'
echo ''
echo ''
echo ''
echo 'docker-compose exec -it odoo_stasis bash'
echo '/stasis'
echo ''
echo ''
echo ''

cat <<EOF > /stasis
cd /opt/asterisk_ari/stasis
pkill -9 -f python.*stasis.py
python stasis.py
EOF
    chmod a+x /stasis

/stasis
