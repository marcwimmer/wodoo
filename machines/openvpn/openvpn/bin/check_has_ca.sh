#!/bin/bash

set -e

if [ ! -f $KEYFOLDER_ROOT/keys/ca.crt ]; then
    echo "Missing CA - please create CA and keys"
    exit -1
fi
