#!/bin/bash
set -x
FILEPATH=/etc/apache2/sites-enabled/000-default.conf

sed -i "s|__SRC_DIR__|${SRC_DIR}|g" "$FILEPATH"

