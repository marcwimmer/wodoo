#!/bin/bash
set -e
set +x

function how_to_use {
    echo How to use:
    echo "1. Walk into the odoo source repo e.g. ~/odoo/customs/c1/odoo"
    echo "2. Edit, commit and remember SHA"
	echo "3. Walk into <module_dir>/patches (create if necessary)"
    echo 4. oepatch.sh SHA description-text
    echo    SHA: the committed sha in git
    echo    description-text: please give a short good name
    echo 5. Reset and forget the patch: git reset --hard HEAD^1
    exit -1
}


if [[ -z "$1" || -z "$2" ]]; then
	how_to_use
	exit -1
fi
DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )

CUSTOMSDIR=$(cd $ODOO_HOME/admin/module_tools; python -c "from odoo_config import get_path_customs_root; print get_path_customs_root()")
PATCHDIR=$(pwd)

PATCHFILE=$PATCHDIR/"$2".patch
cd $CUSTOMSDIR/odoo
git format-patch -1 $1 --stdout > "$PATCHFILE"

echo 
echo
echo
echo Successfully created patch at $PATCHFILE
echo Rewind the odoo src now again e.g.  with 

echo ""
echo ""
read -p "Shall i rewind with git reset --hard HEAD^1 now? [Y/n]" yn
if [[ -z "$yn" || "$yn" == 'y' || "$yn" == 'Y' ]]; then
	cd $CUSTOMSDIR/odoo
	git reset --hard HEAD^1
fi
echo ""
echo 
echo
echo
