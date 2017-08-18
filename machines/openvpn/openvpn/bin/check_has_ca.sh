#!/bin/bash

set -e

if [ ! -f $KEY_DIR/ca.crt ]; then
    echo "Missing CA - please create CA and keys"
    exit -1
fi
