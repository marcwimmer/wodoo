#!/bin/bash
set -e
set -x
[[ "$VERBOSE" == "1" ]] && set +x

# sync source is done by extra machine

POSTGRESBIN=/usr/lib/postgresql/9.5/bin/
PGCONF=/etc/postgresql/9.5/main
DATADIR=/var/lib/postgresql/9.5/main
chown postgres:postgres -R /var/run/postgresql /var/lib/postgresql/9.5/main

# hard way to disable ipv6 usage; rename localhost to 127.0.0.1
tempfile=$(mktemp -u)
grep -v "listen_addresses" < "$PGCONF/postgresql.conf" > "$tempfile"
cp "$tempfile" "$PGCONF/postgresql.conf"
echo "listen_addresses = '127.0.0.1'" >> "$PGCONF/postgresql.conf"


if [[ -d "$DATADIR" ]]; then
	rm -Rf "$DATADIR"
	mkdir -p "$DATADIR"
	chown postgres:postgres -R "$DATADIR"
fi

#echo "host all all 127.0.0.1/32" >> "$PGCONF/pg_hba.conf"
#echo "" >> "$PGCONF/pg_hba.conf"
gosu postgres ${POSTGRESBIN}/initdb -D "$DATADIR" --auth-host=trust --auth-local=trust
sync
sleep 2
pkill -9 -f initdb || true
find /var/run/postgresql -name .s.PGSQL.5432.lock -delete || true
mkdir -p /var/run/postgresql/9.5-main.pg_stat_tmp
chown postgres:postgres /var/run/postgresql -R
sed -i 's/host.*all.*all.*127.*/host all all 127.0.0.1\/32 trust/g' "$PGCONF/pg_hba.conf"
gosu postgres ${POSTGRESBIN}/postgres -D "$DATADIR" -c config_file="$PGCONF/postgresql.conf" &

# wait for postgres
while true;
do
	set +e
	gosu postgres psql -h 127.0.0.1 template1 <<- EOF
	\d
	EOF
	if [[ "$?" == "0" ]]; then
		break
	fi
	set -e
	sleep 1
done

gosu postgres ${POSTGRESBIN}/psql -h 127.0.0.1 template1 < /tmp/init.sql

mkdir /opt/files
chown odoo:odoo /opt/files -R

chmod a+rw /var/run/docker.sock

echo 'Starting odoo gevent'
gosu odoo "/opt/src/odoo/odoo-bin" -c "/opt/config_openerp"  -d "$DBNAME" --log-level="$LOGLEVEL"
