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
for file in docker-compose.odoo docker-compose.ovpn docker-compose.asterisk
do
    sed -e "s/\${DCPREFIX}/$DCPREFIX/" -e "s/\${DCPREFIX}/$DCPREFIX/" config/$file.yml.tmpl > config/$file.yml
    sed -e "s/\${CUSTOMS}/$CUSTOMS/" -e "s/\${CUSTOMS}/$CUSTOMS/" config/$file.yml.tmpl > config/$file.yml
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
    echo "fetch - fetches support data"
    echo "install-telegram-bot - installs required python libs"
    echo "kill - kills running machines"
    echo "logs - show log output; use parameter to specify machine"
    echo "logall - shows log til now; use parameter to specify machine"
    echo "make-CA - recreates CA caution!"
    echo "make-keys - creates VPN Keys for CA, Server, Asterisk and Client. If key exists, it is not overwritten"
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

dc="docker-compose -p $PROJECT_NAME -f config/docker-compose.odoo.yml -f config/docker-compose.ovpn.yml"

RUN_ASTERISK=0

cat customs.env|grep -q 'RUN_ASTERISK=1' && {
    RUN_ASTERISK=1
    dc="$dc -f config/docker-compose.asterisk.yml"
}

CUSTOMSCONF=$DIR/docker-compose-custom.yml
if [[ -f "$CUSTOMSCONF" || -L "$CUSTOMSCONF" ]]; then
    echo "Including $CUSTOMSCONF"
    dc="$dc -f $CUSTOMSCONF"
else
    echo "Not including $CUSTOMSCONF"
fi


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
        /bin/rm -Rf $DIR/support_data/*
    fi
    ;;
fetch)
    echo "Updating support data"
    update_support_data
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
        file=/lib/systemd/system/$servicename

        echo "Setting up upstart script in $file"
        /bin/cp $DIR/config/systemd $file
        /bin/sed -i -e "s/\${DCPREFIX}/$DCPREFIX/" -e "s/\${DCPREFIX}/$DCPREFIX/" $file
        /bin/sed -i -e "s|\${PATH}|$PATH|" -e "s|\${PATH}|$PATH|" $file
        /bin/sed -i -e "s|\${CUSTOMS}|$CUSTOMS|" -e "s|\${CUSTOMS}|$CUSTOMS|" $file

        set +e
        /bin/systemctl disable $servicename
        /bin/rm /etc/systemd/system/$servicename
        /bin/rm lib/systemd/system/$servicename
        /bin/systemctl daemon-reload
        /bin/systemctl reset-failed
        /bin/systemctl enable $servicename
        /bin/systemctl start $servicename
    fi
    ;;
exec)
    $dc exec $2 $3 $3 $4
    ;;
backup_db)
    if [[ -n "$2" ]]; then
        BACKUPDIR=$2
    else
        BACKUPDIR=$DIR/dumps
    fi
    filename=$DBNAME.$(date "+%Y-%m-%d_%H%M%S").dump.gz
    filepath=$BACKUPDIR/$filename
    LINKPATH=$BACKUPDIR/latest_dump
    $dc up -d postgres odoo
    $dc exec postgres /backup.sh
    mv $DIR/dumps/$DBNAME.gz $filepath
    /bin/rm $LINKPATH || true
    ln -s $filepath $LINKPATH
    echo "Dumped to $filepath"
    ;;
backup_files)
    if [[ -n "$2" ]]; then
        BACKUPDIR=$2
    else
        BACKUPDIR=$DIR/dumps
    fi
    # execute in running container via exec
    $dc exec odoo /backup_files.sh

    if [[ "$BACKUPDIR" != "$DIR/dumps" ]]; then
        /usr/bin/rsync $DIR/dumps/$filename.gz $BACKUPDIR -P
        /bin/rm $DIR/dumps/$filename.gz
        /usr/bin/rsync $DIR/dumps/$filename_oefiles $BACKUPDIR -P
        /bin/rm $DIR/dumps/$filename_oefiles
    fi

    echo "Backup files done to $BACKUPDIR/$filename_oefiles"
    ;;
backup)
    if [[ -n "$2" ]]; then
        BACKUPDIR=$2
    else
        BACKUPDIR=$DIR/dumps
    fi
    $DIR/manage.sh backup_db $BACKUPDIR
    $DIR/manage.sh backup_files $BACKUPDIR

    ;;

restore)
    filename_oefiles=oefiles.tar
    VOLUMENAME=${PROJECT_NAME}_postgresdata

    read -p "Deletes database! Continue? Press ctrl+c otherwise"
    if [[ ! -f $2 ]]; then
        echo "File $2 not found!"
        exit -1
    fi
    if [[ -n "$3" && ! -f $3 ]]; then
        echo "File $3 not found!"
        exit -1
    fi

    # remove the postgres volume and reinit
    eval "$dc kill" || true
    $dc rm -f || true
    echo "Removing docker volume postgres-data (irreversible)"
    docker volume ls |grep -q $VOLUMENAME && docker volume rm ${PROJECT_NAME}_postgresdata

    /bin/mkdir -p $DIR/restore
    #/bin/rm $DIR/restore/* || true
    /usr/bin/rsync $2 $DIR/restore/$DBNAME.gz -P
    if [[ -n "$3" && -f "$3" ]]; then
        /usr/bin/rsync $3 $DIR/restore/$filename_oefiles -P
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
    $dc up ${@:2}
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
install-telegram-bot)
    pip install python-telegram-bot
    ;;
purge-source)
    $dc run odoo rm -Rf /opt/openerp/customs/$CUSTOMS
    ;;
update)
    if [[ "$RUN_ASTERISK" == "1" ]]; then
        eval "$dc run ari /init.sh"
        eval "$dc run stasis /init.sh"
    fi
    echo "Run module update"
    if [[ "$RUN_POSTGRES" == "1" ]]; then
    $dc up -d postgres
    fi
    $dc run odoo /update_modules.sh $2
    $dc kill odoo nginx
    if [[ "$RUN_ASTERISK" == "1" ]]; then
        $dc kill ari stasis
    fi
    $dc up -d
    python $DIR/bin/telegram_msg.py "Update done" &> /dev/null
    echo 'Removing unneeded containers'
    $dc rm -f
   ;;
make-CA)
    read -p "Makes all VPN connections invalid! ctrl+c to stop NOW"
    export dc=$dc
    $dc kill ovpn
    $dc run ovpn_ca /root/tools/clean_keys.sh
    $dc run ovpn_ca /root/tools/make_ca.sh
    $dc run ovpn_ca /root/tools/make_server_keys.sh
    $dc rm -f
    ;;
make-keys)
    export dc=$dc
    bash $DIR/config/ovpn/pack.sh
    $dc rm -f
    ;;
*)
    echo "Invalid option $1"
    exit -1
    ;;
esac

if [[ -f config/docker-compose.yml ]]; then
    /bin/rm config/docker-compose.yml || true
fi
