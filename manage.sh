#!/bin/bash
set -e
set +x

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
source $DIR/customs.env
export $(cut -d= -f1 $DIR/customs.env)

echo $DCPREFIX
# replace params in configuration file
cd $DIR
sed -e "s/\${DCPREFIX}/$DCPREFIX/" -e "s/\${DCPREFIX}/$DCPREFIX/" config/docker-compose.yml.tmpl > config/docker-compose.yml

# replace variables in docker-compose;

if [ -z "$1" ]; then
    echo Management of odoo instance
    echo
    echo
    echo First init:
    echo './manage.sh fetch && ./manage.sh init && ./manage.sh setup-startup'
    echo
    echo Update:
    echo './manage.sh update'
    echo
    echo No data is lost at init! Wether oefiles nor database.
    echo
    echo "Please call manage.sh init|springclean|dbinit|update|backup|run_standalone|upall|attach_running|rebuild|restart"
    echo "attach <machine> - attaches to running machine"
    echo
    echo "backup <backup-dir> - backup database and/or files to the given location with timestamp "
    echo
    echo "bash_into <machine-name> - starts /bin/bash for just that machine and connects to it"
    echo
    echo "build - no parameter all machines, first parameter machine name and passes other params; e.g. ./manage.sh build asterisk --no-cache"
    echo
    echo "clean - clears support data"
    echo
    echo "fetch - fetches support data"
    echo
    echo "init <machine-name, empty for all>: depending on machine does basic reinitialization; NO DATA DELETED!"
    echo
    echo "kill - kills running machines"
    echo
    echo "logs - show log output; use parameter to specify machine"
    echo
    echo "springclean - remove dead containers, untagged images, delete unwanted volums"
    echo
    echo "rebuild - rebuilds docker-machines - data not deleted"
    echo
    echo "restart - restarts docker-machines"
    echo
    echo "restore_dump <filename> - restores the given dump as odoo database"
    echo
    echo "setup-startup makes skript in /etc/init/${CUSTOMS}"
    echo
    echo "stop - like docker-compose stop"
    echo
    echo "update - fetch latest source code of modules and run update all on odoo; machines are stopped after that"
    echo
    echo "up - starts all machines equivalent to service <service> start "
    echo
    exit -1
fi

dc="docker-compose -f config/docker-compose.yml"

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
clean)
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
    eval "$dc stop"
    eval "$dc -f config/docker-compose.init.yml up $2"
    ;;

setup-startup)
    file=/etc/init/${CUSTOMS}_odoo.conf
    echo "Setting up startup script in $file"
    PATH=$DIR
    /bin/cp $DIR/config/upstart $file
    /bin/sed -i -e "s/\${DCPREFIX}/$DCPREFIX/" -e "s/\${DCPREFIX}/$DCPREFIX/" $file
    /bin/sed -i -e "s|\${PATH}|$PATH|" -e "s|\${PATH}|$PATH|" $file
    /sbin/initctl reload-configuration
    ;;
backup)
    if [[ -z "$2" ]]; then
        echo "Please suppply backup directory env variable BACKUPDIR!"
        exit -1
    fi
    BACKUPDIR=$2
    docker exec ${DCPREFIX}_odoo_postgres pg_dump $DBNAME -Z1 -Fc -f /opt/dumps/$DBNAME.gz
    filename=$BACKUPDIR/$DBNAME.$(date "+%Y-%m-%d_%H:%M:%S").dump
    mv $DIR/dumps/$DBNAME.gz $filename
    echo "Dumped to $filename"
    # TODO backup files
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
bash_into)
    if [[ -z "$2" ]]; then
        echo "Please give machine name as second parameter e.g. postgres, odoo"
        exit -1
    fi
    set -x
    $dc run "${2}" bash
    ;;
attach)
    if [[ -z "$2" ]]; then
        echo "Please give machine name as second parameter e.g. postgres, odoo"
        exit -1
    fi
    docker exec -it "${DCPREFIX}_${2}" bash
    ;;
rebuild)
    cd $DIR/machines/odoo
    cd $DIR
    eval "$dc stop"
    eval "$dc build --no-cache"
    echo ""
    echo ""
    echo ""
    echo "You should now init everything with ./manage.sh init"
    ;;
build)
    cd $DIR
    eval "$dc build $2 $3 $4"
    ;;
kill)
    cd $DIR
    eval "$dc kill $2 $3"
    ;;
stop)
    cd $DIR
    eval "$dc stop $2 $3 $4"
    ;;
logs)
    cd $DIR
    eval "$dc logs -f $2 $3"
    ;;
restart)
    cd $DIR
    eval "$dc stop"
    eval "$dc up -d"
    ;;
restoredb)
    read -p "Deletes database! Continue? Press ctrl+c otherwise"
    cp $2 ./dumps/$DBNAME.gz
    eval "$dc kill"
    $dc -f config/docker-compose.restoredb.yml up postgres
    ;;
update)
    $dc stop
    $dc -f config/docker-compose.update.yml up odoo
    ;;
*)
    echo "Invalid option $1"
    exit -1
    ;;
esac
