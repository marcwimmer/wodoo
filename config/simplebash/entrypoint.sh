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
    if [[ ! $(getent group "$DUMPS_PATH_GID") && ! $(getent passwd "$DUMPS_PATH_GID") ]]; then
        addgroup -q --gid $DUMPS_PATH_GID dumps_path_group
    fi
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

# set permissions of home folder, otherwise jobber does not like it
chown "$USER" "/home/$USER"

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

# fix permissions on plugins, so that e.g. btrfs.sock is usable
chmod o+rx /run/docker/plugins /run/docker/plugins/* || true
find /run/docker/plugins -name '*.sock' -exec chmod o+rwx {} \;

# export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8
export LANGUAGE=en_US.UTF-8

exec gosu "$USER" "$@"
