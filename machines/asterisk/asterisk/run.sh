#!/bin/bash
rsync /opt/asterisk.base/ /etc/asterisk/ -ar

if [[ -n "$DO_INIT" ]]; then
    git clone git.mt-software.de:/opt/git/openerp/customs/${CUSTOMS}
    cd /opt/$CUSTOMS
    git checkout deploy -f
    [[ -d asterisk ]] && rsync -ar ./asterisk/etc/ /etc/asterisk/
    [[ -d asterisk ]] && rsync ./asterisk/sounds /var/lib/asterisk/sounds/en/
fi

# get latest config
if [[ -n "$DO_UPDATE" ]]; then
    cd /opt/$CUSTOMS
    git pull
    [[ -d /opt/$CUSTOMS/asterisk ]] && rsync /opt/$CUSTOMS/asterisk/etc/ /etc/asterisk/ -ar
fi

[[ ! -d /opt/$CUSTOMS/asterisk ]] && {
    echo "No asterisk directory found in customizations - shutting down"
}

/usr/sbin/asterisk -v > /dev/null
