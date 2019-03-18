#!/bin/bash
export DIR="$(realpath ../..)"
echo $PROJECT_NAME
docker-compose -f docker-compose.yml build cron
