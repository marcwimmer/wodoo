#!/bin/bash
docker exec -it $(docker ps -aqf "name=docker_freepbx") bash
