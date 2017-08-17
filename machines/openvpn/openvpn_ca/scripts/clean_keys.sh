#!/bin/bash
[[ "$VERBOSE" == "1" ]] && set -x
cd $KEYFOLDER
[[ -d keys ]] && {
    cd keys
    rm -rf * .[^.] .??*
}
rm -rf /root/client_out/*
rm -rf /root/server_out/*
rm -rf /root/transfer/*
cd /root/tools

