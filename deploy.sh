#!/bin/bash
set -e
source customs.env
export $(cut -d= -f1 customs.env)
DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )

echo "Host: $SSH_HOST"
echo "Customs: $CUSTOMS"

echo "Checking out customs on remote..."
ssh $SSH_HOST "cd $REMOTEDIR && rm -Rf $CUSTOMS && git clone git.mt-software.de:/git/openerp/customs/$CUSTOMS" 1>/dev/null
echo "Syncing openerp.git on remote..."
ssh $SSH_HOST "cd $REMOTEDIR && rsync git.mt-software.de:/git/openerp/ openerp.git/ -avP --delete" 1>/dev/null
echo "Pulling odoo.git on remote..."
ssh $SSH_HOST "cd $REMOTEDIR/odoo.git && git pull" 1>/dev/null

echo "When newly deployed, then run first build:"
echo "ssh $SSH_HOST"
echo "cd $REMOTEDIR"
echo "./manage.sh build"
