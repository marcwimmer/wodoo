#!/bin/bash
dir="$(pwd)"

function rights() {
	find ./ -type d -exec chmod u=rwx,g=rx,o= '{}' \; 
	find ./ -type f -exec chmod u=rw,g=r,o= '{}' \;
	find ./ -type f -name '*.sh' -exec chmod a+x '{}' \;
	find ./ -type f -name 'update-davical-database' -exec chmod a+x '{}' \;
}

mkdir -p "${SRC_DIR:?}"
rsync /opt/src/ "$SRC_DIR/" -ar
cd "$SRC_DIR" && rights
cd "$dir" || exit 1

[[ -e davical ]] && rm davical -Rf
ln -s "$SRC_DIR/davical/htdocs" davical

chown -R root:www-data .
chown -R root:www-data "$SRC_DIR"
rights
