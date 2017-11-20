#!/bin/bash
set +x
set -e

if [[ "$USER" != "root" ]]; then
	useradd --uid "$UID" --home-dir /opt/external_home "$USER"
	groupadd -g "$DOCKER_GROUP_ID" docker  # to be able to access docker socket
	usermod -aG docker "$USER"
	echo "$USER ALL=NOPASSWD: ALL" >> /etc/sudoers
fi


PGPASSFILE=/tmp/.pgpass
echo "$DB_HOST:$DB_PORT:$DBNAME:$DB_USER:$DB_PWD" > "$PGPASSFILE"
echo "$DB_HOST:$DB_PORT:template1:$DB_USER:$DB_PWD" >> "$PGPASSFILE"
chmod 600 "$PGPASSFILE"
chown "$USER" "$PGPASSFILE"

exec gosu "$USER" "$@"

