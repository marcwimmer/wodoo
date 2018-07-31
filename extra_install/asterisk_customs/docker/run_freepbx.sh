#!/bin/bash
docker-compose kill
docker-compose rm -f
docker-compose build
docker-compose up freepbx-db freepbx-app
