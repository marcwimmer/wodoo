#!/bin/bash
###
#This file lies in odoo
###
set +x
BRANCH="$1"
CMD="$2"
ADDONS_PATH="3"
CONFIG_FILE=/home/odoo/config_migration

sed -i "s|__ADDONS_PATH__|$3|" "$CONFIG_FILE"
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

cd "$ODOO_REPOS_DIRECTORY/OpenUpgrade" || exit 4
set -e
set -x
git checkout "$BRANCH"
pip install git+https://github.com/OCA/openupgradelib.git@master --upgrade
cat "$CONFIG_FILE"
eval sudo -E -H -u "$ODOO_USER" "./$CMD" 
