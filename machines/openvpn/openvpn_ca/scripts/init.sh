#!/bin/bash
set -e
rsync /root/openvpn-ca-tmpl/ /root/openvpn-ca/ -arL
