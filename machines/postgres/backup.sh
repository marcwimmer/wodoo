#!/bin/bash
set -e
set +x
pg_dump -Z0 -Fc $DBNAME | pigz --rsyncable > /opt/dumps/$DBNAME.gz
