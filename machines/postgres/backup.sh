#!/bin/bash
set -e
set -x
whoami
pg_dump $DBNAME -Z1 -Fc -f /opt/dumps/$DBNAME.gz
