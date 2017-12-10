#!/bin/bash
echo "Adapting the default asterisk configuration for individual needs:"
DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )

DESTINATION="$DIR/etc/asterisk"
SOURCE="$DIR/etc_default"

echo "Copying latest default config"
rsync "$SOURCE/" "$DESTINATION/" -ar -delete

if [[ "$( find "$DESTINATION" -type f |wc -l )" == "0" ]]; then
	echo "No asterisk configuration found in $DESTINATION - copying default there"
	rsync "$SOURCE/" "$DESTINATION/" -ar
fi

sed -i 's/^bindaddr=.*/bindaddr=0.0.0.0/g' "$DESTINATION/http.conf"
