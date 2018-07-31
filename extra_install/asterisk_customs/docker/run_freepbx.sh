#!/bin/bash
docker-compose kill
docker-compose rm -f
docker-compose build
docker-compose up -d freepbx-db
docker-compose up freepbx-app
