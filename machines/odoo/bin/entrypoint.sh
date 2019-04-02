#!/bin/bash
set +x

if [[ -z "$OWNER_UID" ]]; then
    echo "Please set setting OWNER_UID"
    exit -1
fi

sed -i "s/1000:1000/$OWNER_UID:$OWNER_UID/g" /etc/passwd
chown $OWNER_UID:$OWNER_UID /home/odoo -R

python3 /apply-env-to-config.py

exec "$@"
