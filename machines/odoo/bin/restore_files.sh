#!/bin/bash
set -e
set -x

/set_permissions.sh
tar vxfz /opt/restore/$filename -C /
