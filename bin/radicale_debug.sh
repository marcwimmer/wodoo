#!/bin/bash
source name-tab radicale
echo "run /run.sh inside the container"
docker-compose run -p5232:5232 radicale bash
