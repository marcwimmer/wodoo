#!/bin/bash
set -e
set +x

function how_to_use {
    echo How to use:
    echo 1. Walk into the odoo source repo e.g. ~/odoo/customs/c1/odoo
    echo 2. Edit and commitand remember sha
    echo 3. oepatch.sh SHA description-text
    echo    SHA: the committed sha in git
    echo    description-text: please give a short good name
    echo 4. Reset and forget the patch: git reset --hard HEAD^1
    exit -1
}


if [[ -z "$1" || -z "$2" ]]; then
    how_to_use
    exit -1
fi
DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )

CUSTOMSDIR=$ODOO_HOME/customs/$(cat $ODOO_HOME/vimtriggers/current_customs)
PATCHDIR=$CUSTOMSDIR/patches/$(cat $CUSTOMSDIR/.version)

mkdir -p $PATCHDIR

PATCHFILE=$PATCHDIR/$2.patch
git format-patch -1 $1 --stdout > $PATCHFILE

echo 
echo
echo
echo Successfully created patch at $PATCHFILE
echo Rewind the odoo src now again e.g.
echo with git reset --hard HEAD^1
echo
echo
