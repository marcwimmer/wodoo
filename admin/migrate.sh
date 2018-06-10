#!/bin/bash
###
#This file lies in odoo
###
set -x
/apply-env-to-config.sh

if [[ "$RUN_MIGRATION" != "1" ]]; then
    echo "RUN_MIGRATION not set!"
    exit 1
fi

if [[ -z "$1" ]]; then
    echo "Please provide branch"
    exit 1
fi
if [[ -z "$2" ]]; then
    echo "Please provide command"
    exit 1
fi
BRANCH="$1"
CMD="$2"

cd "$ODOO_REPOS_DIRECTORY/OpenUpgrade" || exit 4
set -e
set -x
git checkout "$BRANCH"
#pip install openupgradelib
pip install git+https://github.com/OCA/openupgradelib.git@master --upgrade
eval sudo -E -H -u "$ODOO_USER" "./$CMD" 
