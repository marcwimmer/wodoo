#!/bin/bash
docker exec -it $(docker ps -qf "name=docker_freepbx") bash
