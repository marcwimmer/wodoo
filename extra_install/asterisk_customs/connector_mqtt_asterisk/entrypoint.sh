#!/bin/bash
export DOCKER_HOST='123'
GATEWAY=$(route -n | sed -n 3p | awk '{ print $2 }')
export DOCKER_HOST=$GATEWAY
echo "To debug this application, run:"
echo "/app.py"
exec "$@"
