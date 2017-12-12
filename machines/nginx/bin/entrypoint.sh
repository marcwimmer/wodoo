#!/bin/bash

chmod a+x /opt/bin/*.sh

cp /opt/bin/hot_reload.sh /hot_reload.sh

exec "$@"
