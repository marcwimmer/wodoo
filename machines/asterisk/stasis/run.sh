#!/bin/bash
set -e
set -x

git config --system user.name $GIT_USER_NAME
git config --system user.email $GIT_USER_EMAIL
git config --system push.default simple

/usr/sbin/nginx
cd /opt/src
[ ! -d asterisk_ari ] && {
    git clone git.mt-software.de:/git/openerp/modules/asterisk_ari
}

echo 'fetching latest stasis version from deploy'
cd asterisk_ari
git checkout -f deploy
git pull


cd /opt/src/asterisk_ari/stasis
python stasis.py &

set +x
while true;
do
    pgrep -f stasis.py > /dev/null || {
	[[ ! -f /tmp/debugging ]] && {
	    echo 'Stasis seems dead and no debugging'
	    exit -1
	}
    }
    sleep 1
done
