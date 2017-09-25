#!/bin/bash
set -e

echo "Installing version $1 requirements"
wget https://raw.githubusercontent.com/odoo/odoo/"$1"/requirements.txt -O /root/"requirements_$1".txt
pip install -r /root/"requirements_$1.txt"
