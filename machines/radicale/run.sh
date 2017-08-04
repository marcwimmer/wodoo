#!/bin/bash

if [[ "$RUN_RADICALE" != "1" ]]; then
    echo 'Radicale is turned off by customs.env'
    exit 0
fi


#copy config template to destination and adjust settings
cp /etc/radicale/config.template /etc/radicale/config
sed -i "s/__DB__/$DBNAME/g" /etc/radicale/config
sed -i "s/__USER__/$RADICALE_USER/g" /etc/radicale/config
sed -i "s/__PASSWORD__/$RADICALE_PASSWORD/g" /etc/radicale/config

cd $RADICALE_DIR/$RADICALE_VERSION
export PYTHONPATH=.:$RADICALE_DIR/$VERSION/rc
echo 'Starting Radicale ...'
python radicale.py -C /etc/radicale/config
