#!/bin/bash
set -e
set +x

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
source $DIR/customs.env
export $(cut -d= -f1 $DIR/customs.env)

# replace params in configuration file
# replace variables in docker-compose;
cd $DIR
echo "ODOO VERSION from customs.env $ODOO_VERSION"
for file in docker-compose.odoo docker-compose.asterisk
do
    sed -e "s/\${DCPREFIX}/$DCPREFIX/" -e "s/\${DCPREFIX}/$DCPREFIX/" config/$file.yml.tmpl > config/$file.yml
done
sed -e "s/\${ODOO_VERSION}/$ODOO_VERSION/" -e "s/\${ODOO_VERSION}/$ODOO_VERSION/" machines/odoo/Dockerfile.template > machines/odoo/Dockerfile
sync

if [ -z "$1" ]; then
    echo Management of odoo instance
    echo
    echo
    echo First init:
    echo './manage.sh fetch && ./manage.sh update && ./manage.sh setup-startup'
    echo
    echo Update:
    echo './manage.sh update [module]'
    echo 'Just custom modules are updated, never the base modules (e.g. prohibits adding old stock-locations)'
    echo 'Minimal downtime - but there is a downtime, even for phones'
    echo 
    echo "Quick Pull (just pulls source codes for e.g. mako"
    echo './manage.sh quickupdate [module]'
    echo
    echo "Please call manage.sh springclean|update|backup|run_standalone|upall|attach_running|rebuild|restart"
    echo "attach <machine> - attaches to running machine"
    echo "backup <backup-dir> - backup database and/or files to the given location with timestamp; if not directory given, backup to dumps is done "
    echo "debug <machine-name> - starts /bin/bash for just that machine and connects to it; if machine is down, it is powered up; if it is up, it is restarted; as command an endless bash loop is set"
    echo "build - no parameter all machines, first parameter machine name and passes other params; e.g. ./manage.sh build asterisk --no-cache"
    echo "clean_supportdata - clears support data"
    echo "clean_supportdata - clears support data"
    echo "fetch - fetches support data"
    echo "kill - kills running machines"
    echo "logs - show log output; use parameter to specify machine"
    echo "logall - shows log til now; use parameter to specify machine"
    echo "make-keys - creates VPN Keys for CA, Server, Asterisk and Client."
    echo "springclean - remove dead containers, untagged images, delete unwanted volums"
    echo "rm - command"
    echo "rebuild - rebuilds docker-machines - data not deleted"
    echo "restart - restarts docker-machine(s) - parameter name"
    echo "restore <filepathdb> <filepath_tarfiles>- restores the given dump as odoo database"
    echo "runbash <machine name> - starts bash in NOT RUNNING container (a separate one)"
    echo "setup-startup makes skript in /etc/init/${CUSTOMS}"
    echo "stop - like docker-compose stop"
    echo "quickpull - fetch latest source, oeln - good for mako templates"
    echo "update <machine name>- fetch latest source code of modules and run update of just custom modules; machines are restarted after that"
    echo "up - starts all machines equivalent to service <service> start "
    echo
    exit -1
fi

dc="docker-compose -f config/docker-compose.odoo.yml"

cat customs.env|grep -q 'RUN_ASTERISK=1' && {
    dc="$dc -f config/docker-compose.asterisk.yml"
}



function update_support_data {
    SUPPORTDIR=$DIR/support_data
    if [[ ! -d "$SUPPORTDIR" ]]; then
        mkdir $SUPPORTDIR
    fi
    cd $SUPPORTDIR
    echo "Syncing openerp.git..."
    rsync git.mt-software.de:/git/openerp/ openerp.git -ar

    echo "Checking for odoo.git..."
    if [[ ! -d "odoo.git" ]]; then
        echo "Cloning odoo.git..."
        git clone https://github.com/odoo/odoo odoo.git
    else
        echo "Pulling odoo.git..."
        cd odoo.git
        git pull
    fi
}


case $1 in
clean_supportdata)
    echo "Deleting support data"
    if [[ -d $DIR/support_data ]]; then
        rm -Rf $DIR/support_data/*
    fi
    ;;
fetch)
    echo "Updating support data"
    update_support_data
    ;;
init)
    cd $DIR
    eval "$dc run odoo /init.sh full"
    eval "$dc run ari /init.sh full"
    eval "$dc run stasis /init.sh full"
    eval "$dc stop"
    eval "$dc start"
    ;;

setup-startup)
    PATH=$DIR

    if [[ -f /sbin/initctl ]]; then
        # ubuntu 14.04 upstart
        file=/etc/init/${CUSTOMS}_odoo.conf

        echo "Setting up upstart script in $file"
        /bin/cp $DIR/config/upstart $file
        /bin/sed -i -e "s/\${DCPREFIX}/$DCPREFIX/" -e "s/\${DCPREFIX}/$DCPREFIX/" $file
        /bin/sed -i -e "s|\${PATH}|$PATH|" -e "s|\${PATH}|$PATH|" $file
        /bin/sed -i -e "s|\${CUSTOMS}|$CUSTOMS|" -e "s|\${CUSTOMS}|$CUSTOMS|" $file
        /sbin/initctl reload-configuration
    else
        echo "Setting up systemd script for startup"
        servicename=${CUSTOMS}_odoo.service
        file=/etc/systemd/system/$servicename

        echo "Setting up upstart script in $file"
        /bin/cp $DIR/config/systemd $file
        /bin/sed -i -e "s/\${DCPREFIX}/$DCPREFIX/" -e "s/\${DCPREFIX}/$DCPREFIX/" $file
        /bin/sed -i -e "s|\${PATH}|$PATH|" -e "s|\${PATH}|$PATH|" $file
        /bin/sed -i -e "s|\${CUSTOMS}|$CUSTOMS|" -e "s|\${CUSTOMS}|$CUSTOMS|" $file

        /bin/systemctl daemon-reload
        /bin/systemctl enable $servicename
        /bin/systemctl start $servicename
    fi
    ;;
backup)
    if [[ -n "$2" ]]; then
        BACKUPDIR=$2
    else
        BACKUPDIR=$DIR/dumps
    fi
    filename=$DBNAME.$(date "+%Y-%m-%d_%H%M%S").dump.gz
    filepath=$BACKUPDIR/$filename
    filename_oefiles=oefiles.tar

    $dc exec postgres /backup.sh
    mv $DIR/dumps/$DBNAME.gz $filepath
    echo "Dumped to $filepath"

    echo "Backuping files..."

    # execute in running container via exec
    $dc run -e filename=$filename_oefiles odoo /backup_files.sh

    if [[ "$BACKUPDIR" != "$DIR/dumps" ]]; then
        cp $DIR/dumps/$filename.gz $BACKUPDIR
        rm $DIR/dumps/$filename.gz
        cp $DIR/dumps/$filename_oefiles $BACKUPDIR
        rm $DIR/dumps/$filename_oefiles
    fi
    echo "Backup files done to $BACKUPDIR/$filename_oefiles"
    ;;

restore)
    filename_oefiles=oefiles.tar

    read -p "Deletes database! Continue? Press ctrl+c otherwise"
    if [[ ! -f $2 ]]; then
        echo "File $2 not found!"
        exit -1
    fi
    if [[ -n "$3" && ! -f $3 ]]; then
        echo "File $3 not found!"
        exit -1
    fi
    mkdir -p $DIR/restore
    rm $DIR/restore/* || true
    cp $2 $DIR/restore/$DBNAME.gz
    if [[ -n "$3" && -f "$3" ]]; then
        cp $3 $DIR/restore/$filename_oefiles
    fi

    echo "Shutting down containers"
    eval "$dc kill"

    $dc run postgres /restore.sh

    if [[ -n "$3" ]]; then
        echo 'Extracting files...'
        $dc run -e filename=$filename_oefiles odoo /restore_files.sh
    fi

    echo ''
    echo 'Restart systems by ./manage restart'
    ;;

springclean)
    #!/bin/bash
    echo removing dead containers
    docker rm $(docker ps -a -q)

    echo Remove untagged images
    docker images | grep "<none>" | awk '{ print "docker rmi " $3 }' | bash

    echo "delete unwanted volumes (can pass -dry-run)"
    docker rmi $(docker images -q -f='dangling=true')
    ;;
up)
    $dc up $2 $3 $4
    ;;
debug)
    if [[ -z "$2" ]]; then
        echo "Please give machine name as second parameter e.g. postgres, odoo"
        exit -1
    fi
    $dc kill $2
    echo "${DCPREFIX}_${2}"
    sed "s/TEMPLATE/${2}/g" $DIR/config/docker-compose.debug.tmpl.yml > $DIR/config/docker-compose.debug.yml
    eval "$dc -f $DIR/config/docker-compose.debug.yml up -d $2"
    docker exec -it "${DCPREFIX}_${2}" bash
    ;;
attach)
    if [[ -z "$2" ]]; then
        echo "Please give machine name as second parameter e.g. postgres, odoo"
        exit -1
    fi
    docker exec -it "${DCPREFIX}_${2}" bash
    ;;
runbash)
    if [[ -z "$2" ]]; then
        echo "Please give machine name as second parameter e.g. postgres, odoo"
        exit -1
    fi
    eval "$dc run $2 bash"
    ;;
rebuild)
    cd $DIR/machines/odoo
    cd $DIR
    eval "$dc build --no-cache $2"
    ;;
build)
    cd $DIR
    eval "$dc $@"
    ;;
kill)
    cd $DIR
    eval "$dc kill $2 $3 $4 $5 $6 $7 $8 $9"
    ;;
stop)
    cd $DIR
    eval "$dc stop $2 $3 $4"
    ;;
logs)
    cd $DIR
    eval "$dc logs --tail=400 -f $2 $3"
    ;;
logall)
    cd $DIR
    eval "$dc logs -f $2 $3"
    ;;
rm)
    cd $DIR
    $dc $@
    ;;
restart)
    cd $DIR
    eval "$dc stop $2"
    eval "$dc up -d $2"
    ;;
update)
    eval "$dc run ari /init.sh"
    eval "$dc run stasis /init.sh"
    $dc kill odoo
    $dc run odoo /update_src.sh
    $dc run odoo /update_modules.sh $3
    $dc kill odoo ari stasis
    $dc up -d
   ;;
quickpull)
    # useful for updating just mako templates
    $dc run odoo /update_src.sh
   ;;
make-keys)
    export dc=$dc
    bash $DIR/config/ovpn/pack.sh keys
    ;;
*)
    echo "Invalid option $1"
    exit -1
    ;;
esac

if [[ -f config/docker-compose.yml ]]; then
    rm config/docker-compose.yml || true
fi
