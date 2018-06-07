#!/bin/bash
[[ "$VERBOSE" == "1" ]] && set -x

DESTFILE="/opt/dumps/$1"
tar cfz "$DESTFILE" /opt/files
if [[ -n "$LINUX_OWNER_CREATED_BACKUP_FILES" ]]; then
	chown "$LINUX_OWNER_CREATED_BACKUP_FILES" "$DESTFILE"
fi
