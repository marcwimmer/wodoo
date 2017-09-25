#!/bin/bash
set -e
set -x
[[ "$VERBOSE" == "1" ]] && set +x

# sync source is done by extra machine

POSTGRESBIN=/usr/lib/postgresql/9.5/bin/
mkdir -p /var/run/postgresql/9.5-main.pg_stat_tmp
mkdir -p /var/lib/postgresql/9.5/main
chown postgres:postgres -R /var/run/postgresql /var/lib/postgresql/9.5/main

gosu postgres ${POSTGRESBIN}/postgres -D /var/lib/postgresql/9.5/main -c config_file=/etc/postgresql/9.5/main/postgresql.conf &

# wait for postgres
while true;
do
	set +e
	gosu postgres psql template1 <<- EOF
	\d
	EOF
	if [[ "$?" == "0" ]]; then
		break
	fi
	set -e
	sleep 1
done

gosu postgres ${POSTGRESBIN}/psql template1 < /tmp/init.sql

mkdir /opt/files
chown odoo:odoo /opt/files -R

echo 'Starting odoo gevent'
gosu odoo "/opt/src/odoo/odoo-bin" -c "/opt/config_openerp"  -d "$DBNAME" --log-level="$LOGLEVEL"
