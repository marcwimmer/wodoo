#!/bin/bash
#copy default sounds

if [[ "$RUN_ASTERISK" == "0" ]]; then
    echo "asterisk is turned off by customs.env - good bye! :)"
    exit 0
fi

rsync /opt/default_sounds /var/lib/asterisk/sounds/ -ar
cd /var/lib/asterisk/sounds

function extract_lang() {
    mkdir -p $1
    cd $1
    unzip /opt/default_sounds/$1/core.zip
    unzip /opt/default_sounds/$1/extra.zip
}
extract_lang de

#copy default configuration
rsync /opt/etc.base/ /etc/asterisk/ -ar

if [[ -n "$DO_INIT" ]]; then
    cd /opt
    [[ -d "${CUSTOMS}" ]] && rm -Rf ${CUSTOMS}
    git clone git.mt-software.de:/opt/git/openerp/customs/${CUSTOMS}
    cd /opt/$CUSTOMS
    git checkout deploy -f
fi

# get latest config
if [[ -n "$DO_UPDATE" || -n "$DO_INIT" ]]; then
    cd /opt/$CUSTOMS
    git pull
    [[ -d asterisk ]] && rsync ./asterisk/etc/ /etc/asterisk/ -ar
    [[ -d asterisk ]] && rsync ./asterisk/sounds/ /var/lib/asterisk/sounds/ -ar
    echo "done updating asterisk"
    exit 0
fi

#copy music on hold
rsync /opt/$CUSTOMS/asterisk/moh_custom/ /var/lib/asterisk/moh_custom/ -ar

[[ ! -d /opt/$CUSTOMS/asterisk ]] && {
    echo "No asterisk directory found in customizations - shutting down"
    exit 0
}


/usr/sbin/asterisk -vvvvv -ddddd
