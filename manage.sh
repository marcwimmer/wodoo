#!/bin/bash
set -e
set +x

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
source $DIR/customs.env
export $(cut -d= -f1 $DIR/customs.env)

if [ -z "$1" ]; then
    echo Management of odoo instance
    echo
    echo "Please call manage.sh init|springclean|dbinit|update|backup|run_standalone|upall|attach_running|rebuild|restart"
    echo "attach <machine> - attaches to running machine"
    echo "backup <backup-dir> - backup database and/or files to the given location with timestamp "
    echo "bash_into <machine-name> - starts /bin/bash for just that machine and connects to it"
    echo "dbinit - recreates database CAREFUL: ctrl+c to abort - all data gone "
    echo "init: "
    echo "springclean - remove dead containers, untagged images, delete unwanted volums"
    echo "rebuild - rebuilds docker-machines - data not deleted"
    echo "restart - restarts docker-machines"
    echo "setup-startup-script - makes skript in /etc/init/odoo"
    echo "update - fetch latest source code of modules and run update all on odoo; machines are stopped after that"
    echo "upall - starts all machines equivalent to service <service> start "
    echo "kill - kills running machines"
    exit -1
fi

dc="docker-compose -f config/docker-compose.yml"

function update_support_data {
    SUPPORTDIR=$DIR/support_data
    if [[ ! -d "$SUPPORTDIR" ]]; then
        mkdir $SUPPORTDIR
    fi
    cd $SUPPORTDIR
    rsync git.mt-software.de:/git/openerp/ openerp.git -ar

    if [[ ! -d "odoo.git" ]]; then
        git clone https://github.com/odoo/odoo odoo.git
    else
        cd odoo.git
        git pull
    fi
}


case $1 in
init)
    update_support_data
    cd $DIR
    eval "$dc stop"
    eval "$dc -f config/docker-compose.init.yml up odoo"
    ;;

setup-startup-script)
    echo "Setting up startup script in /etc/init"
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
upall)
    $dc up -d
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
dbinit)
    read -p "Init deletes database! Continue? Press ctrl+c otherwise"
    $dc kill
    $dc -f config/docker-compose.dbinit.yml up postgres
    ;;
rebuild)
    cd $DIR/machines/odoo
    # TODO move into docker file/run.sh
    [ -f requirements.txt ] && rm requirements.txt
    wget https://raw.githubusercontent.com/odoo/odoo/$ODOO_VERSION/requirements.txt
    cd $DIR
    eval "$dc stop"
    eval "$dc build --no-cache"
    eval "$dc -f config/docker-compose.init.yml up odoo"
    ;;
build)
    cd $DIR
    eval "$dc stop"
    eval "$dc build"
    ;;
kill)
    cd $DIR
    eval "$dc kill"
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
