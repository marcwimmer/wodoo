#!/bin/bash
[[ "$VERBOSE" == "1" ]] && set -x

DESTFILE="/opt/dumps/$1"
tar cfz "$DESTFILE" /opt/files
