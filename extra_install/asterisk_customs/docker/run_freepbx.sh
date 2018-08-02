#!/bin/bash
docker-compose kill freepbx
docker-compose rm -f freepbx
docker-compose build freepbx
docker-compose up -d freepbx

echo "Now goto http://localhost:9080 and setup username password."
