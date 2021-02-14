#!/bin/bash
set -x
set -eux

service nginx start
wssh --address=0.0.0.0 --port=8080
