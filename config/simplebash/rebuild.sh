#!/bin/bash
export DIR="$(realpath ../..)"
echo $PROJECT_NAME
docker build --tag "${PROJECT_NAME}_simplebash" .
docker-compose -f docker-compose.yml build simplebash
#docker-compose -f docker-compose-cron.yml build cron
