#!/bin/bash

[[ -f "/run/pid" ]] && {

    ifconfig || grep tun && {
        exit 0
    } || {
        exit -1
    }

} || {
    exit -1
}
