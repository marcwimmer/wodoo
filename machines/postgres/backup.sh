#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x

DESTFILE=/opt/dumps/$DBNAME.gz

if [ "$(id -u)" = '0' ]; then
	#root user
	gosu postgres "$BASH_SOURCE" "$@" #restart self (like they do in entry point)
	echo "Moving dump to share..."
	mv /tmp/dump $DESTFILE

	if [[ -n "$LINUX_OWNER_CREATED_BACKUP_FILES" ]]; then
		chown $LINUX_OWNER_CREATED_BACKUP_FILES $DESTFILE
	fi
	echo "Dumped $DBNAME!"
else
	#postgres user
	echo "Dumping $DBNAME to $DESTFILE..."
	pg_dump -Z0 -Fc $DBNAME | pigz --rsyncable > /tmp/dump || echo 'fehler!!!!!!!!!!!!!!!!!!!!!!!!'
fi
