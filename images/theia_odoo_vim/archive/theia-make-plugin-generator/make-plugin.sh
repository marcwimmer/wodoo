#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"
set -e
echo "USER_ID=$(id -u)" > .env
docker-compose build
docker-compose run --rm yo yo @theia/plugin

echo ""
echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
echo "Adapt package.json to work:"
echo "..."
echo "devDependencies": {
echo '"@types/node": "12.12.6",'
echo "}"