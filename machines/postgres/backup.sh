#!/bin/bash
set -e
set -x
pg_dump $DBNAME -Z1 -Fc -f /opt/dumps/$filename.gz
