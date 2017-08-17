#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x
rsync /root/openvpn-ca-tmpl/ /root/openvpn-ca/ -arL --delete
