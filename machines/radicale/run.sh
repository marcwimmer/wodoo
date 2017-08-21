#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x

if [[ "$RUN_RADICALE" != "1" ]]; then
    echo 'Radicale is turned off by settings'
    exit 0
fi


#copy config template to destination and adjust settings
cp /etc/radicale/config.template /etc/radicale/config
sed -i "s/__DB__/$DBNAME/g" /etc/radicale/config
sed -i "s/__USER__/$RADICALE_USER/g" /etc/radicale/config
sed -i "s/__PASSWORD__/$RADICALE_PASSWORD/g" /etc/radicale/config
sed -i "s/__ODOO_HOST__/$RADICALE_ODOO_HOST/g" /etc/radicale/config
sed -i "s/__ODOO_PORT__/$RADICALE_ODOO_PORT/g" /etc/radicale/config

cd $RADICALE_DIR
find -name '*.pyc' -delete
cd $RADICALE_DIR/$ODOO_VERSION/$RADICALE_VERSION
export PYTHONPATH=.:$RADICALE_DIR/$ODOO_VERSION/RadicaleCustomizations
echo 'Starting Radicale ...'
python radicale.py -C /etc/radicale/config



