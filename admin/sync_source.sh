#!/bin/bash
set +x
PID_FILE="$TMPDIR/$DC_PREFIX_sync_source.pid"

if [[ -f "$PID_FILE" ]]; then
	pgrep -q -F "$PID_FILE" && {
		echo "Killing existing fswatchsync"
		pkill -F "$PID_FILE"  > /dev/null
		res=$?
		if [[ "$res" == "0" ]]; then
			echo "Successfully killed"
			rm "$PID_FILE"
		else
			echo "$res"
			echo "Error killing current process"
			exit 2
		fi
	}
fi
echo $$ > "$PID_FILE"

remote_loc=rsync://127.0.0.1:10874/odoo/
exclude="--exclude=.git"

ODOO_BASE="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )/.."
ODOO_BASE="$(readlink -f "$ODOO_BASE")"
CUSTOMS="$1"
CUSTOMS_DIR="$ODOO_BASE/data/src/customs/$CUSTOMS/" 

if [[ -z "$1" ]]; then
	echo "Please provide customs as parameter1"
	exit 5
fi
cd "$ODOO_BASE" || exit 3
echo "Initial complete sync of sources"
NO_SYNC=1 ./odoo up -d odoo_source_syncer

cd "$CUSTOMS_DIR" || exit 4
while true;
do
	rsync "$CUSTOMS_DIR" "$remote_loc" -arP "$exclude" --delete-after && break
	sleep 1
done

echo "Watching directory $CUSTOMS_DIR for changes"

# copy file at once (first rsync); delete deleted files later in background
fswatch -0 -l 0.1 -e .git/ -e .pyc  "$CUSTOMS_DIR" | \
	xargs -0 -n 1 -I {} bash -c 'rsync --quiet --relative -avz "${1/$3/}" "$2" "$4"; rsync --relative -avz --delete-after "$(dirname "${1/$3/}")/" "$2" "$4" &' - '{}' "$remote_loc" "$CUSTOMS_DIR" "$exclude"
