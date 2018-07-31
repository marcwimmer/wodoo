#!/bin/bash
docker-compose kill
docker-compose rm -f
docker-compose build
docker-compose up -d freepbx-db
sleep 5
docker-compose up freepbx-app
