#!/bin/bash
set -e
set +x
source customs.env
export $(cut -d= -f1 customs.env)

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )

if [ -z "$1" ]; then
    echo Management of odoo instance
    echo
    echo "Please call manage.sh init|springclean|dbinit|update|backup|run_standalone|upall|attach_running|rebuild|restart"
    exit -1
fi

dc="docker-compose -f config/docker-compose.yml"


case $1 in
backup)
    if [[ -z "$BACKUPDIR" ]]; then
        echo "Please suppply backup directory env variable BACKUPDIR!"
        exit -1
    fi
    docker exec ${DCPREFIX}_odoo_postgres pg_dump $DBNAME -Z1 -Fc -f /opt/dumps/$DBNAME.gz
    filename=$BACKUPDIR/$DBNAME.$(date "+%Y-%m-%d_%H:%M:%S").dump
    mv $DIR/dumps/$DBNAME.gz $filename
    echo "Dumped to $filename"
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
run_standalone)
    if [[ -z "$2" ]]; then
        echo "Please give machine name as second parameter e.g. postgres, odoo"
        exit -1
    fi
    set -x
    $dc run "${2}" bash
    ;;
attach_running)
    if [[ -z "$2" ]]; then
        echo "Please give machine name as second parameter e.g. postgres, odoo"
        exit -1
    fi
    docker exec -it "${DCPREFIX}_${2}" bash
    ;;
dbinit)
    read -p "Init deletes database! Continue? Press ctrl+c otherwise"
    $dc kill
    $dc -f config/docker-compose.$1.yml up postgres
    ;;
rebuild)
    cd $DIR/machines/odoo
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
init)
    cd $DIR
    eval "$dc stop"
    eval "$dc -f config/docker-compose.$1.yml up odoo"
    ;;

kill)
    cd $DIR
    eval "$dc kill"
    ;;

update)
    $dc stop
    $dc -f config/docker-compose.$1.yml up odoo
    ;;
*)
    echo "Invalid option $1"
    exit -1
    ;;
esac
