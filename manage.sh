#!/bin/bash
# Basic Rules:
# - if a command would stop production run, then ask to continue is done before
set -e
set +x

args=("$@")
DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
ALL_PARAMS=${@:2} # all parameters without command


function default_confs() {
	export ODOO_FILES=$DIR/data/odoo.files
}

function export_customs_env() {
    # set variables from customs env
    while read line; do
        # reads KEY1=A GmbH and makes export KEY1="A GmbH" basically
        [[ "$line" == '#*' ]] && continue
        [[ "$line" == '' ]] && continue
        var="${line%=*}"
        value="${line##*=}"
        eval "$var=\"$value\""
    done <$DIR/customs.env
    export $(cut -d= -f1 $DIR/customs.env)  # export vars now in local variables
}


function askcontinue() {
    echo ""
    echo ""
    read -p "Continue? (Ctrl+C to break)" || {
    exit -1
    }
}

function showhelp() {
    echo Management of odoo instance
    echo
    echo
    echo Reinit fresh db:
    echo './manage.sh reset-db'
    echo
    echo Update:
    echo './manage.sh update [module]'
    echo 'Just custom modules are updated, never the base modules (e.g. prohibits adding old stock-locations)'
    echo 'Minimal downtime - but there is a downtime, even for phones'
    echo 
    echo "Please call manage.sh springclean|update|backup|run_standalone|upall|attach_running|rebuild|restart"
    echo "attach <machine> - attaches to running machine"
    echo "backup <backup-dir> - backup database and/or files to the given location with timestamp; if not directory given, backup to dumps is done "
    echo "debug <machine-name> - starts /bin/bash for just that machine and connects to it; if machine is down, it is powered up; if it is up, it is restarted; as command an endless bash loop is set"
    echo "build - no parameter all machines, first parameter machine name and passes other params; e.g. ./manage.sh build asterisk --no-cache"
    echo "clean_supportdata - clears support data"
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
    echo "restore <filepathdb> <filepath_tarfiles> [-force] - restores the given dump as odoo database"
    echo "restore-dev-db - Restores database dump regularly and then applies scripts to modify it, so it can be used for development (adapting mailserver, disable cronjobs)"
    echo "runbash <machine name> - starts bash in NOT RUNNING container (a separate one)"
    echo "runbash-with-ports <machine name> - like runbash but connects the ports; debugging ari/stasis and others"
    echo "setup-startup makes skript in /etc/init/${CUSTOMS}"
    echo "stop - like docker-compose stop"
    echo "quickpull - fetch latest source, oeln - good for mako templates"
    echo "update <machine name>- fetch latest source code of modules and run update of just custom modules; machines are restarted after that"
    echo "update-source - sets the latest source code in the containers"
    echo "up - starts all machines equivalent to service <service> start "
    echo
}

if [ -z "$1" ]; then
    showhelp
    exit -1
fi

function prepare_filesystem() {
    mkdir -p $DIR/run/config
}


function prepare_yml_files_from_template_files() {
    # replace params in configuration file
    # replace variables in docker-compose;
    cd $DIR
    echo "CUSTOMS: $CUSTOMS"
    echo "DB: $DBNAME"
    echo "VERSION: $ODOO_VERSION"
    ALL_CONFIG_FILES=$(cd config; ls |grep '.*docker-compose.*tmpl' | sed 's/\.yml\.tmpl//g') 
    FILTERED_CONFIG_FILES=""
    for file in $ALL_CONFIG_FILES 
    do
        # check if RUN_ASTERISK=1 is defined, and then add it to the defined machines; otherwise ignore

        #docker-compose.odoo --> odoo
        S="${file/docker-compose/''}"
        S=(${S//-\./ })
        S=${S[-1]}
        S=${S/-/_} # substitute - with _ otherwise invalid env-variable
        S="RUN_${S^^}"  #RUN_odoo ---> RUN_ODOO

        ENV_VALUE=${!S}  # variable indirection; get environment variable

        if [[ "$ENV_VALUE" == "" ]] || [[ "$ENV_VALUE" == "1" ]]; then

            FILTERED_CONFIG_FILES+=$file
            FILTERED_CONFIG_FILES+=','
            DEST_FILE=$DIR/run/$file.yml
            cp config/$file.yml.tmpl $DEST_FILE
            sed -i -e "s/\${DCPREFIX}/$DCPREFIX/" -e "s/\${DCPREFIX}/$DCPREFIX/" $DEST_FILE
            sed -i -e "s/\${CUSTOMS}/$CUSTOMS/" -e "s/\${CUSTOMS}/$CUSTOMS/" $DEST_FILE
        fi
    done
    sed -e "s/\${ODOO_VERSION}/$ODOO_VERSION/" -e "s/\${ODOO_VERSION}/$ODOO_VERSION/" machines/odoo/Dockerfile.template > machines/odoo/Dockerfile

    all_config_files="$(for f in ${FILTERED_CONFIG_FILES//,/ }; do echo "-f run/$f.yml"; done)"
    all_config_files=$(echo "$all_config_files"|tr '\n' ' ')
    dc="docker-compose -p $PROJECT_NAME $all_config_files"
}



function include_customs_conf_if_set() {
    # odoo customs can provide custom docker machines
    CUSTOMSCONF=$DIR/docker-compose-custom.yml
    if [[ -f "$CUSTOMSCONF" || -L "$CUSTOMSCONF" ]]; then
        echo "Including $CUSTOMSCONF"
        dc="$dc -f $CUSTOMSCONF"
    fi
}


function do_command() {
    case $1 in
    clean_supportdata)
        echo "Deleting support data"
        if [[ -d $DIR/support_data ]]; then
            /bin/rm -Rf $DIR/support_data/*
        fi
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
        LINKPATH=$DIR/dumps/latest_dump
        $dc up -d postgres odoo
        # by following command the call is crontab safe;
        # there is a bug: https://github.com/docker/compose/issues/3352
        docker exec -i $($dc ps -q postgres) /backup.sh
        mv $DIR/dumps/$DBNAME.gz $filepath
        /bin/rm $LINKPATH || true
        ln -s $filepath $LINKPATH
        md5sum $filepath
        echo "Dumped to $filepath"
        ;;
    backup_files)
        if [[ -n "$2" ]]; then
            BACKUPDIR=$2
        else
            BACKUPDIR=$DIR/dumps
        fi
        BACKUP_FILENAME=oefiles.$CUSTOMS.tar
        BACKUP_FILEPATH=$BACKUPDIR/$BACKUP_FILENAME

        # execute in running container via exec
        # by following command the call is crontab safe;
        # there is a bug: https://github.com/docker/compose/issues/3352
        docker exec -i $($dc ps -q odoo) /backup_files.sh
        [[ -f $BACKUP_FILEPATH ]] && rm -Rf $BACKUP_FILEPATH
        mv $DIR/dumps/oefiles.tar $BACKUP_FILEPATH

        echo "Backup files done to $BACKUPDIR/$filename_oefiles"
        ;;
    backup)
        if [[ -n "$2" && "$2" != "only-db" ]]; then
            BACKUPDIR=$2
        else
            BACKUPDIR=$DIR/dumps
        fi

        $DIR/manage.sh backup_db $BACKUPDIR
        echo "$*" |grep -q 'only-db' || {
            $DIR/manage.sh backup_files $BACKUPDIR
        }

        ;;
    reset-db)
        [[ $last_param != "-force" ]] && {
            echo "Deletes database $DBNAME!"
            askcontinue
        }
        echo "Stopping all services and creating new database"
        echo "After creation the database container is stopped. You have to start the system up then."
        $dc kill
        $dc run -e INIT=1 postgres /entrypoint2.sh
        echo
        echo 
        echo
        echo "Database initialized. You have to restart now."

        ;;

    restore)
        filename_oefiles=oefiles.tar
        VOLUMENAME=${PROJECT_NAME}_postgresdata

        last_index=$(echo "$# - 1"|bc)
        last_param=${args[$last_index]}

        [[ $last_param != "-force" ]] && {
            read -p "Deletes database $DBNAME! Continue? Press ctrl+c otherwise"
        }
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

        if [[ -n "$3" && "$3" != "-force" ]]; then
            echo 'Extracting files...'
            $dc run -e filename=$filename_oefiles odoo /restore_files.sh
        fi

        echo ''
        echo 'Restart systems by ./manage restart'
        ;;

    springclean)
        docker system prune

        echo removing dead containers
        docker rm $(docker ps -a -q)

        echo Remove untagged images
        docker images | grep "<none>" | awk '{ print "docker rmi " $3 }' | bash

        echo "delete unwanted volumes (can pass -dry-run)"
        docker rmi $(docker images -q -f='dangling=true')
        ;;
    up)
        $dc up $ALL_PARAMS
        ;;
    debug)
        if [[ -z "$2" ]]; then
            echo "Please give machine name as second parameter e.g. postgres, odoo"
            exit -1
        fi
        echo "Current machine $2 is dropped and restartet with service ports in bash. Usually you have to type /debug.sh then."
        askcontinue
        # shutdown current machine and start via run and port-mappings the replacement machine
        $dc kill $2
        cd $DIR

        #execute self
        $0 runbash-with-ports $2 /bin/bash
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
    runbash-with-ports)
        if [[ -z "$2" ]]; then
            echo "Please give machine name as second parameter e.g. postgres, odoo"
            exit -1
        fi
        eval "$dc run --service-ports $2 bash"
        ;;
    rebuild)
        cd $DIR/machines/odoo
        cd $DIR
        eval "$dc build --no-cache $2"
        ;;
    build)
        cd $DIR
        eval "$dc build $ALL_PARAMS"
        ;;
    kill)
        cd $DIR
        eval "$dc kill $2 $3 $4 $5 $6 $7 $8 $9"
        ;;
    stop)
        cd $DIR
        eval "$dc stop $2 $3 $4"
        ;;
    logsn)
        cd $DIR
        eval "$dc logs --tail=$2 -f -t $3 $4"
        ;;
    logs)
        cd $DIR
        lines="${@: -1}"
        if [[ -n ${lines//[0-9]/} ]]; then
            lines="5000"
        else
            echo "Showing last $lines lines"
        fi
        eval "$dc logs --tail=$lines -f -t $2 "
        ;;
    logall)
        cd $DIR
        eval "$dc logs -f -t $2 $3"
        ;;
    rm)
        cd $DIR
        $dc rm $ALL_PARAMS
        ;;
    restart)
        cd $DIR
        eval "$dc kill $2"
        eval "$dc up -d $2"
        ;;
    install-telegram-bot)
        pip install python-telegram-bot
        ;;
    purge-source)
        $dc run odoo rm -Rf /opt/openerp/customs/$CUSTOMS
        ;;
    update-source)
        if [[ -z "$2" ]]; then
            $dc up source_code
        else
            echo $2 > /tmp/last
            $dc run source_code /sync_source.sh $2
        fi
        ;;
    update)
        echo "Run module update"
        date +%s > /var/opt/odoo-update-started
        if [[ "$RUN_POSTGRES" == "1" ]]; then
        $dc up -d postgres
        fi
        $dc kill odoo_cronjobs # to allow update of cronjobs (active cronjob, cannot update otherwise)
        $dc kill odoo_update
        $dc rm -f odoo_update
        $dc up -d postgres && sleep 3

        set -e
        # sync source
        $dc up source_code
        set +e

        $dc run odoo_update /update_modules.sh $2
        $dc kill odoo nginx
        if [[ "$RUN_ASTERISK" == "1" ]]; then
            $dc kill ari stasis
        fi
        $dc kill odoo
        $dc rm -f
        $dc up -d
        python $DIR/bin/telegram_msg.py "Update done" &> /dev/null
        echo 'Removing unneeded containers'
        $dc kill nginx
        $dc up -d
        df -h / # case: after update disk / was full

       ;;
    make-CA)
        echo '!!!!!!!!!!!!!!!!!!'
        echo '!!!!!!!!!!!!!!!!!!'
        echo '!!!!!!!!!!!!!!!!!!'
        echo
        echo
        echo "Extreme Caution!"
        echo 
        echo '!!!!!!!!!!!!!!!!!!'
        echo '!!!!!!!!!!!!!!!!!!'
        echo '!!!!!!!!!!!!!!!!!!'

        askcontinue
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
    restore-dev-db)
        #!/bin/bash

        echo "Restores dump to locally installed postgres and executes to scripts to adapt user passwords, mailservers and cronjobs"
        DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
        cd $DIR
        SQLFILE=machines/postgres/turndb2dev.sql
        DB=$(basename $1)
        DB=${DB%.*}
        exit -1


        if [[ -z "$1" ]]; then
            echo "File missing! Please provide per parameter 1"
            exit -1
        fi

        source .env
        DB_HOST=$DB_HOST_EXT
        echo "Using $DB_HOST, $DB_PORT"

        export PGPASSWORD=$DB_PASSWORD
        ARGS="-h $DB_HOST -p $DB_PORT -U $DB_USER"
        PSQL="psql $ARGS"
        DROPDB="dropdb $ARGS"
        CREATEDB="createdb $ARGS"
        PGRESTORE="pg_restore $ARGS"

        echo "Databasename is $DB"
        eval "$DROPDB $DB" || echo "Failed to drop $DB"
        set -ex
        eval "$CREATEDB $DB"
        eval "$PGRESTORE -d $DB $1" || {
            gunzip -c $1 | $PGRESTORE -d $DB
        }

        if [[ "$2" != "nodev" ]]; then
            eval "$PSQL $DB" < $SQLFILE
        fi
        ;;
    export-i18n)
        LANG=$2
        MODULES=$3
        if [[ -z "$MODULES" ]]; then
            echo "Please define at least one module"
            exit -1
        fi
        rm $DIR/run/i18n/* || true
        chmod a+rw $DIR/run/i18n
        $dc run odoo_lang_export /export_i18n.sh $LANG $MODULES
        # file now is in $DIR/run/i18n/export.po
        ;;
    import-i18n)
        $dc run odoo /import_i18n.sh $ALL_PARAMS
        ;;
    *)
        echo "Invalid option $1"
        exit -1
        ;;
    esac
}


function cleanup() {

    if [[ -f config/docker-compose.yml ]]; then
        /bin/rm config/docker-compose.yml || true
    fi
}

function sanity_check() {
    if [[ ("$RUN_POSTGRES" == "1" || -z "$RUN_POSTGRES") && $DB_HOST != 'postgres' ]]; then
        echo "You are using the docker postgres container, but you do not have the DB_HOST set to use it."
        echo "Either configure DB_HOST to point to the docker container or turn it off by: "
        echo 
        echo "RUN_POSTGRES=0"
        exit -1
    fi

	if [[ -d $ODOO_FILES ]]; then
		if [[ "$(stat -c "%u" $ODOO_FILES)" != "1000" ]]; then
			chown 1000 $ODOO_FILES
		fi
	fi
}

default_confs
export_customs_env
prepare_filesystem
prepare_yml_files_from_template_files
include_customs_conf_if_set
sanity_check
do_command "$@"
cleanup

