#!/bin/bash
set -x
set -e
DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
dockerconfig=docker-compose.override.yml
cp $dockerconfig.tmpl $dockerconfig
sed -i.bak "s|IN|$DIR/|g" $dockerconfig
sed -i.bak "s|OUT|$DIR/build/|g" $dockerconfig
FILES="-f builder/docker-compose.yml -f docker-compose.override.yml"
docker-compose $FILES up
rm $dockerconfig $dockerconfig.bak
$(which chromium-browser) ./build/index.html
