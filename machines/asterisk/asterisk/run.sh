#!/bin/bash
rsync /opt/etc.base/ /etc/asterisk/ -ar

if [[ -n "$DO_INIT" ]]; then
    cd /opt
    git clone git.mt-software.de:/opt/git/openerp/customs/${CUSTOMS}
    cd /opt/$CUSTOMS
    git checkout deploy -f
fi

# get latest config
if [[ -n "$DO_UPDATE" || -n "$DO_INIT" ]]; then
    cd /opt/$CUSTOMS
    git pull
    [[ -d asterisk ]] && rsync ./asterisk/etc/ /etc/asterisk/ -ar
    [[ -d asterisk ]] && rsync ./asterisk/sounds /var/lib/asterisk/sounds/en/ -ar
    echo "done updating asterisk"
    exit 0
fi

[[ ! -d /opt/$CUSTOMS/asterisk ]] && {
    echo "No asterisk directory found in customizations - shutting down"
    exit 0
}

/usr/sbin/asterisk -vvvvv -ddddd
