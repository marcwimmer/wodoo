#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"
set -e
echo "USER_ID=$(id -u)" > .env
echo "DOCKER_GROUP_ID=$(cut -d: -f3 < <(getent group docker))" >> .env
docker-compose build
docker-compose kill
docker-compose down
docker-compose up -d
