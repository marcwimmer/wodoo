#!/bin/bash
set -e
set -x 

echo "Installing custom requirements from odoo"


#7.0
if [[ "$1" == "7.0" ]]; then
    echo "Installing version 7.0 requirements"
    pip install -r /root/requirements_70.txt
elif [[ "$1" == "6.1" ]]; then
    echo "Installing version 6.1 requirements - but nothing set"
    # use same requirements...
    pip install -r /root/requirements_70.txt
else
    echo "Installing version $1 requirements"
    wget https://raw.githubusercontent.com/odoo/odoo/$1/requirements.txt -O /root/requirements_$1.txt
    pip install -r /root/requirements_$1.txt
fi

pip install -r /root/requirements.txt
