#!/bin/bash
set -e
[[ -d "$PATH_CA_TEMPLATE" ]] && rm -Rf $PATH_CA_TEMPLATE
make-cadir $PATH_CA_TEMPLATE
rsync $PATH_CA_TEMPLATE/ $EASY_RSA/ -arL
rm -Rf $PATH_CA_TEMPLATE
sync
