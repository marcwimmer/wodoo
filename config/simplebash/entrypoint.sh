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
mkdir -p /home/$USER/.config
if [[ -e /root/.config/pudb/pudb.cfg ]]; then
    mkdir -p /home/$USER/.config/pudb
    cp /root/.config/pudb/pudb.cfg /home/$USER/.config/pudb/pudb.cfg
fi
chown "$USER":"$USER" /home/$USER/.config -R

#copy docker config
mkdir -p /home/$USER/.docker
cp /tmp/docker.config /home/$USER/.docker/config.json
chown "$USER":"$USER" /home/$USER/.docker -R

# add 999 group for vboxsf access
if [[ "$DUMPS_PATH_GID" ]]; then
    getent group "$DUMPS_PATH_GID" || addgroup -q --gid $DUMPS_PATH_GID dumps_path_group
    usermod -aG $DUMPS_PATH_GID $USER
fi

# transfer git settings
for file in .gitconfig .ssh; do
    if [[ -d "/opt/external_home/$file" ]]; then
        rsync "/opt/external_home/$file/" "/home/$USER/$file" -ar
        chown -R "$USER" /home/$USER/$file

    elif [[ -f "/opt/external_home/$file" ]]; then
         cp "/opt/external_home/$file" "/home/$USER/$file"
         chown -R "$USER" /home/$USER/$file
    fi
done

PGPASSFILE=/tmp/.pgpass
echo "$DB_HOST:$DB_PORT:$DBNAME:$DB_USER:$DB_PWD" > "$PGPASSFILE"
echo "$DB_HOST:$DB_PORT:template1:$DB_USER:$DB_PWD" >> "$PGPASSFILE"
if [[ -n "$CALENDAR_DB_HOST" ]]; then
    echo "$CALENDAR_DB_HOST:$CALENDAR_DB_PORT:$CALENDAR_DB_NAME:$CALENDAR_DB_USER:$CALENDAR_DB_PWD" >> "$PGPASSFILE"
fi
chmod 600 "$PGPASSFILE"
chown "$USER" "$PGPASSFILE"

# fix docker problem (otherwise logging fails)
chmod a+w /dev/stdout

exec gosu "$USER" "$@"
