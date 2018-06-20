#!/bin/bash
set +x
set -e

if [[ "$USER" != "root" && "$USER" != "" ]]; then
	if [[ "$PLATFORM" == "macos" ]]; then
		useradd --uid "$UID" "$USER"
		chown "$USER" /var/run/docker.sock
		usermod -aG daemon "$USER"
	else
		#useradd --uid "$UID" --home-dir /opt/external_home "$USER"
		useradd --uid "$UID" "$USER"
		groupname="docker"
		groupadd -g "$DOCKER_GROUP_ID" "$groupname"  # to be able to access docker socket
		usermod -aG docker "$USER"
	fi
	echo "$USER ALL=NOPASSWD: ALL" >> /etc/sudoers
fi

#copy pudb
mkdir -p /home/$USER/.config/pudb
cp /root/.config/pudb/pudb.cfg /home/$USER/.config/pudb/pudb.cfg
chown "$USER":"$USER" /home/$USER/.config -R


PGPASSFILE=/tmp/.pgpass
echo "$DB_HOST:$DB_PORT:$DBNAME:$DB_USER:$DB_PWD" > "$PGPASSFILE"
echo "$DB_HOST:$DB_PORT:template1:$DB_USER:$DB_PWD" >> "$PGPASSFILE"
if [[ "$CALENDAR_DB_HOST" ]]; then
    echo "$CALENDAR_DB_HOST:$CALENDAR_DB_PORT:$CALENDAR_DB_NAME:$CALENDAR_DB_USER:$CALENDAR_DB_PWD" >> "$PGPASSFILE"
fi
chmod 600 "$PGPASSFILE"
chown "$USER" "$PGPASSFILE"

# fix docker problem (otherwise logging fails)
chmod a+w /dev/stdout

exec gosu "$USER" "$@"
