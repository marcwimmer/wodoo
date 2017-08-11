#!/bin/bash
[[ "$VERBOSE" == "1" ]] && set -x

/set_permissions.sh
DESTFILE=/opt/dumps/odoofiles.tar
tar cfz $DESTFILE /opt/files
if [[ -n "$LINUX_OWNER_CREATED_BACKUP_FILES" ]]; then
	chown $LINUX_OWNER_CREATED_BACKUP_FILES $DESTFILE
fi
