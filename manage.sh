#!/bin/bash
# Basic Rules:
# - if a command would stop production run, then ask to continue is done before
# - if in set -e environment and piping commands like cat ... |psql .. then use: pipe=$(mktemp -u); mkfifo $pipe; do.. > $pipe &; do < $pipe
#
# Important Githubs:
#   * https://github.com/docker/compose/issues/2293  -> /usr/local/bin/docker-compose needed
#   * there is a bug: https://github.com/docker/compose/issues/3352  --> using -T
#
function dcrun() {
	$dc run -T "$@"
}

function dcexec() {
	$dc exec -T "$@"
}

function startup() {
	args=("$@")
	echo $args
	DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
	ALL_PARAMS=${@:2} # all parameters without command
	export odoo_manager_started_once=1

}

function default_confs() {
	export FORCE_CONTINUE=0
	export ODOO_FILES=$DIR/data/odoo.files
	export ODOO_UPDATE_START_NOTIFICATION_TOUCH_FILE=$DIR/run/update_started
	export RUN_POSTGRES=1
	export DB_PORT=5432
	export ALLOW_DIRTY_ODOO=0 # to modify odoo source it may be dirty
	if [[ -z "$ODOO_HOME" ]]; then
		export ODOO_HOME=/opt/odoo
	fi
	FORCE=0
	echo "$*" |grep -q '[-]force' && {
		FORCE=1
	}

	if [[ -z "$FORCE_UNVERBOSE" ]]; then
		FORCE_UNVERBOSE=0
	fi
	echo "$*" |grep -q '[-]unverbose' && {
		FORCE_UNVERBOSE=1
	}

}

function export_settings() {
    # set variables from settings
    while read line; do
        # reads KEY1=A GmbH and makes export KEY1="A GmbH" basically
        [[ "$line" == '#*' ]] && continue
        [[ "$line" == '' ]] && continue
        var="${line%=*}"
        value="${line##*=}"
        eval "$var=\"$value\""
    done <$DIR/settings
    export $(cut -d= -f1 $DIR/settings)  # export vars now in local variables

	if [[ "$RUN_POSTGRES" == "1" ]]; then
		DB_HOST=postgres
		DB_PORT=5432
		DB_USER=odoo
		DB_PWD=odoo
	fi

	# get odoo version
	export ODOO_VERSION=$(
	cd $ODOO_HOME/admin/module_tools
	python <<-EOF
	import odoo_config
	v = odoo_config.get_version_from_customs("$CUSTOMS")
	print v
	EOF
	)

	# set odoo version in settings file for machines
	$(
cd $ODOO_HOME/admin/module_tools
python <<- END
import odoo_config
env = odoo_config.get_env()
env['ODOO_VERSION'] = "$ODOO_VERSION"
env.write()
	END
	)

	if [[ "$FORCE_UNVERBOSE" == "1" ]]; then
		VERBOSE=0
	fi

	[[ "$VERBOSE" == "1" ]] && set -x

}

function restore_check() {
	dumpname=$(basename $2)
	if [[ ! "${dumpname%.*}" == *"$DBNAME"* ]]; then
		echo "The dump-name \"$dumpname\" should somehow match the current database \"$DBNAME\", which isn't."
		exit -1
	fi

}

function exists_db() {
	sql="select 'database_exists' from pg_database where datname='$DBNAME'"
	[[ -n "$(FORCE_UNVERBOSE=1 echo $sql| $0 psql template1 | grep 'database_exists')" ]] && {
		echo 'database exists'
	} || {
		echo 'database does not exist'
	}
}

function remove_postgres_connections() {
	echo "Removing all current connections"

	[[ "$(exists_db)" == "database does not exist" ]] || {
		return 
	}

	SQL=$(cat <<-EOF
		SELECT pg_terminate_backend(pg_stat_activity.pid)
		FROM pg_stat_activity 
		WHERE pg_stat_activity.datname = '$DBNAME' 
		AND pid <> pg_backend_pid(); 
		EOF
		)
	echo "$SQL" | $0 psql
}

function do_restore_db_in_docker_container () {
	# remove the postgres volume and reinit

	echo "Restoring dump within docker container postgres"
	dump_file=$1
	$dc kill
	$dc rm -f || true
	if [[ "$RUN_POSTGRES" == 1 ]]; then
		askcontinue "Removing docker volume postgres-data (irreversible)"
	fi
	VOLUMENAME=${PROJECT_NAME}_postgresdata
	docker volume ls |grep -q $VOLUMENAME && docker volume rm $VOLUMENAME 
	LOCAL_DEST_NAME=$DIR/run/restore/$DBNAME.gz
	[[ -f "$LOCAL_DEST_NAME" ]] && rm $LOCAL_DEST_NAME

	/bin/ln $dump_file $LOCAL_DEST_NAME
	$0 reset-db
	dcrun postgres /restore.sh $(basename $LOCAL_DEST_NAME)
}

function do_restore_db_on_external_postgres () {
	echo "Restoring dump on $DB_HOST"
	dump_file=$1
	echo "Using Host: $DB_HOST, Port: $DB_PORT, User: $DB_USER, ...."
	export PGPASSWORD=$DB_PWD
	ARGS="-h $DB_HOST -p $DB_PORT -U $DB_USER"
	PSQL="psql $ARGS"
	DROPDB="dropdb $ARGS"
	CREATEDB="createdb $ARGS"
	PGRESTORE="pg_restore $ARGS"

	remove_postgres_connections
	eval "$DROPDB --if-exists $DBNAME" || echo "Failed to drop $DBNAME"
	eval "$CREATEDB $DBNAME"
	pipe=$(mktemp -u)
	mkfifo "$pipe"
	gunzip -c $1 > $pipe &
	echo "Restoring Database $DBNAME"
	$PGRESTORE -d $DBNAME < $pipe
}

function do_restore_files () {
	# remove the postgres volume and reinit
	tararchive_full_path=$1
	LOCAL_DEST_NAME=$DIR/run/restore/odoofiles.tar
	[[ -f "$LOCAL_DEST_NAME" ]] && rm $LOCAL_DEST_NAME

	/bin/ln $tararchive_full_path $LOCAL_DEST_NAME
	dcrun odoo /bin/restore_files.sh $(basename $LOCAL_DEST_NAME)
}

function askcontinue() {
	if [[ "$1" != "-force" ]]; then
		echo $1
	fi
	force=0
	echo "$*" |grep -q '[-]force' && {
		force=1
	}
	if [[ "$force" == "1" || "$FORCE" == "1" || "$FORCE_CONTINUE" == "1" ]]; then
		# display prompt
		echo "Ask continue disabled, continuing..."
	else
		read -p "Continue? (Ctrl+C to break)" || {
			exit -1
		}
	fi
}

function showhelp() {
    echo Management of odoo instance
    echo
    echo
	echo ./manage.sh install-deps
	echo ./manage.sh sanity-check
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
	echo ""
    echo "backup <backup-dir> - backup database and/or files to the given location with timestamp; if not directory given, backup to dumps is done "
	echo ""
    echo "backup-db <backup-dir>"
	echo ""
    echo "backup-files <backup-dir>"
	echo ""
    echo "debug <machine-name> - starts /bin/bash for just that machine and connects to it; if machine is down, it is powered up; if it is up, it is restarted; as command an endless bash loop is set"
	echo ""
    echo "build - no parameter all machines, first parameter machine name and passes other params; e.g. ./manage.sh build asterisk --no-cache"
	echo ""
    echo "install-telegram-bot - installs required python libs; execute as sudo"
	echo ""
    echo "telegram-setup- helps creating a permanent chatid"
	echo ""
    echo "kill - kills running machines"
	echo ""
    echo "logs - show log output; use parameter to specify machine"
	echo ""
    echo "logall - shows log til now; use parameter to specify machine"

	echo ""
	echo "---------------------------------------------------------------"
	echo "OVPN"
	echo ""
    echo "make-CA - recreates CA caution! for asterisk domain e.g. provide parameter "asterisk""
    echo "make-phone-CA - recreates CA caution!"
    echo "show-openvpn-ciphers - lists the available ciphers"
    echo "enter-VPN <domain> - starts machine and you have some tools like nmap"
	echo ""
	echo "---------------------------------------------------------------"
	echo ""
    echo "springclean - remove dead containers, untagged images, delete unwanted volums"
	echo ""
    echo "rm - command"
	echo ""
    echo "rebuild - rebuilds docker-machines - data not deleted"
	echo ""
    echo "restart - restarts docker-machine(s) - parameter name"
	echo ""
    echo "restore <filepathdb> <filepath_tarfiles> [-force] - restores the given dump as odoo database"
	echo ""
    echo "restore-dev-db - Restores database dump regularly and then applies scripts to modify it, so it can be used for development (adapting mailserver, disable cronjobs)"
	echo ""
    echo "runbash <machine name> - starts bash in NOT RUNNING container (a separate one)"
	echo ""
    echo "setup-startup makes skript in /etc/init/${CUSTOMS}"
	echo ""
    echo "stop - like docker-compose stop"
	echo ""
    echo "quickpull - fetch latest source, oeln - good for mako templates"
	echo ""
	echo "turn-into-dev - applies scripts to make the database a dev database"
	echo ""
    echo "update <machine name>- fetch latest source code of modules and run update of just custom modules; machines are restarted after that"
	echo ""
    echo "up - starts all machines equivalent to service <service> start "
	echo ""
	echo "remove-web-assets - if odoo-web interface is broken (css, js) then purging the web-assets helps; they are recreated on odoo restart"
	echo ""
	echo "fix-permissions - sets user 1000 for odoo and odoo_files"
	echo ""
	echo "make-customs"
    echo
}

if [ -z "$1" ]; then
    showhelp
    exit -1
fi

function prepare_filesystem() {
    mkdir -p $DIR/run/config
}

function replace_all_envs_in_file() {
	if [[ ! -f "$1" ]]; then
		echo "File not found: $1"
		exit -1
	fi
	export FILENAME=$1
	$(python <<-"EOF"
	import os
	import re
	filepath = os.environ['FILENAME']
	with open(filepath, 'r') as f:
	    content = f.read()
	all_params = re.findall(r'\$\{[^\}]*?\}', content)
	for param in all_params:
	    name = param
	    name = name.replace("${", "")
	    name = name.replace("}", "")
	    content = content.replace(param, os.environ[name])
	with open(filepath, 'w') as f:
	    f.write(content)
	EOF
	)
}

function prepare_yml_files_from_template_files() {
    # replace params in configuration file
    # replace variables in docker-compose;
    cd $DIR

	if [[ "$odoo_manager_started_once" != "1" ]]; then
		echo "CUSTOMS: $CUSTOMS"
		echo "DB: $DBNAME"
		echo "VERSION: $ODOO_VERSION"
		echo "FILES: $ODOO_FILES"
	fi

	# python: find all configuration files from machines folder; extract sort 
	# by manage-sort flag and put file into run directory
	# only if RUN_parentpath like RUN_ODOO is <> 0 include the machine
	#
	# - also replace all environment variables
	find $DIR/run -name *docker-compose*.yml -delete
	ALL_CONFIG_FILES=$(cd $DIR; find machines -name 'docker-compose*.yml')
	ALL_CONFIG_FILES=$(ALL_CONFIG_FILES=$ALL_CONFIG_FILES python $DIR/bin/prepare_dockercompose_files.py)
	cd $DIR
    for file in $ALL_CONFIG_FILES; do
		replace_all_envs_in_file run/$file
    done

	# translate config files for docker compose with appendix -f
    ALL_CONFIG_FILES="$(for f in ${ALL_CONFIG_FILES}; do echo "-f run/$f" | tr '\n' ' '; done)"

	# append custom docker composes
	if [[ -n "$ADDITIONAL_DOCKER_COMPOSE" ]]; then
		cp $ADDITIONAL_DOCKER_COMPOSE $DIR/run
		for file in $ADDITIONAL_DOCKER_COMPOSE; do
			ALL_CONFIG_FILES+=" -f "
			ALL_CONFIG_FILES+=$file
		done
	fi
	echo $ALL_CONFIG_FILES

    dc="/usr/local/bin/docker-compose -p $PROJECT_NAME $ALL_CONFIG_FILES"
}


function do_command() {
    case $1 in
		install-deps)
			apt install -y python-psycopg2 python-pip pigz
			pip install pip --upgrade
			pip install lxml
			pip install configobj
			pip install unidecode
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
    backup-db)
        if [[ -n "$2" ]]; then
            BACKUPDIR=$2
        else
            BACKUPDIR=$DIR/dumps
        fi
        filename=$DBNAME.$(date "+%Y-%m-%d_%H%M%S").dump.gz
        filepath=$BACKUPDIR/$filename
        LINKPATH=$DIR/dumps/latest_dump
		if [[ "$RUN_POSTGRES" == "1" ]]; then
			$dc up -d postgres odoo
			# by following command the call is crontab safe;
			docker exec -i $($dc ps -q postgres) /backup.sh
			mv $DIR/dumps/$DBNAME.gz $filepath
		else
			pg_dump -Z0 -Fc $DBNAME | pigz --rsyncable > $filepath
		fi
        /bin/rm $LINKPATH || true
        ln -s $filepath $LINKPATH
        md5sum $filepath
        echo "Dumped to $filepath"
        ;;
    backup-files)
        if [[ -n "$2" ]]; then
            BACKUPDIR=$2
        else
            BACKUPDIR=$DIR/dumps
        fi
        BACKUP_FILENAME=$CUSTOMS.files.tar.gz
        BACKUP_FILEPATH=$BACKUPDIR/$BACKUP_FILENAME

		dcrun odoo /backup_files.sh
        [[ -f $BACKUP_FILEPATH ]] && rm -Rf $BACKUP_FILEPATH
        mv $DIR/dumps/odoofiles.tar $BACKUP_FILEPATH

        echo "Backup files done to $BACKUP_FILEPATH"
        ;;

    backup)
		$0 backup-db $ALL_PARAMS
		$0 backup-files $ALL_PARAMS
        ;;
    reset-db)
		echo "$*" |grep -q '[-]force' || {
            askcontinue "Deletes database $DBNAME!"
		}
		if [[ "$RUN_POSTGRES" != "1" ]]; then
			echo "Postgres container is disabled; cannot reset external database"
			exit -1
		fi
        echo "Stopping all services and creating new database"
        echo "After creation the database container is stopped. You have to start the system up then."
        $dc kill
        dcrun -e INIT=1 postgres /entrypoint2.sh
        echo
        echo 
        echo
        echo "Database initialized. You have to restart now."

        ;;

	restore-files)
		set -e
        if [[ -z "$2" ]]; then
			echo "Please provide the tar file-name."
			exit -1
        fi
		echo 'Extracting files...'
		do_restore_files $2
		;;

	restore-db)
		set -e
		restore_check $@
		dumpfile=$2

		echo "$*" |grep -q '[-]force' || {
			askcontinue "Deletes database $DBNAME!"
		}

		if [[ "$RUN_POSTGRES" == "1" ]]; then
			do_restore_db_in_docker_container $dumpfile
		else
			askcontinue "Trying to restore database on remote database. Please make sure, that the user $DB_USER has enough privileges for that."
			do_restore_db_on_external_postgres $dumpfile
		fi
		set_db_ownership

		;;
	set_db_ownership)
		set_db_ownership
		;;

    restore)

        if [[ ! -f $2 ]]; then
            echo "File $2 not found!"
            exit -1
        fi
        if [[ -n "$3" && ! -f $3 ]]; then
            echo "File $3 not found!"
            exit -1
        fi

		dumpfile=$2
		tarfiles=$3

		$0 restore-db $dumpfile
		
		if [[ "$tarfiles" == "[-]force" ]]; then
			tarfiles=""
		fi

        if [[ -n "$tarfiles" ]]; then
			$0 restore-files $tarfiles
        fi

		$0 fix-permissions

        echo "Restart systems by $0 restart"
        ;;
    restore-dev-db)
		if [[ "$ALLOW_RESTORE_DEV" ]]; then
			echo "ALLOW_RESTORE_DEV must be explicitly allowed."
			exit -1
		fi
        echo "Restores dump to locally installed postgres and executes to scripts to adapt user passwords, mailservers and cronjobs"
		restore_check $@
		$0 restore-db $ALL_PARAMS
		$0 turn-into-dev $ALL_PARAMS

        ;;
	turn-into-dev)
		if [[ "$DEVMODE" != "1" ]]; then
			echo "When applying this sql scripts, the database is not usable anymore for production environments. "
			echo "Please set DEVMODE=1 to allow this"
			exit -1
		fi
        SQLFILE=machines/postgres/turndb2dev.sql
		$0 psql < $SQLFILE
		
		;;
	psql)
		# gets sql query from pipe
		# check if there is a pipe argument
		[[ ! -t 0 ]] && {  # checks if there is pipe data https://unix.stackexchange.com/questions/33049/check-if-pipe-is-empty-and-run-a-command-on-the-data-if-it-isnt
			sql=$(cat /dev/stdin)
		} || {
			sql=""
		}

		if [[ "$RUN_POSTGRES" == "1" ]]; then
			dcexec postgres bash -c "/bin/echo \"$sql\" | gosu postgres psql $ALL_PARAMS"
		else
			export PGPASSWORD=$DB_PWD
			echo "$sql" | psql -h $DB_HOST -p $DB_PORT -U $DB_USER -w $DBNAME $ALL_PARAMS
		fi 
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
		set_db_ownership
        $dc up $ALL_PARAMS
        ;;
    debug)
		# puts endless loop into container command and then attaches to it;
		# by this, name resolution to the container still works
        if [[ -z "$2" ]]; then
            echo "Please give machine name as second parameter e.g. postgres, odoo"
            exit -1
        fi
		set_db_ownership
        echo "Current machine $2 is dropped and restartet with service ports in bash. Usually you have to type /debug.sh then."
        askcontinue
        # shutdown current machine and start via run and port-mappings the replacement machine
        $dc kill $2
        cd $DIR
		DEBUGGING_COMPOSER=$DIR/run/debugging.yml
		cp $DIR/config/debugging/template.yml $DEBUGGING_COMPOSER
		sed -i -e "s/\${DCPREFIX}/$DCPREFIX/" -e "s/\${NAME}/$2/" $DEBUGGING_COMPOSER
		dc="$dc -f $DEBUGGING_COMPOSER"  # command now has while loop

        #execute self
		$dc up -d $2
		$0 attach $2 

        ;;
    attach)
        if [[ -z "$2" ]]; then
            echo "Please give machine name as second parameter e.g. postgres, odoo"
            exit -1
        fi
		display_machine_tips $2
        $dc exec $2 bash
        ;;
    runbash)
		set_db_ownership
        if [[ -z "$2" ]]; then
            echo "Please give machine name as second parameter e.g. postgres, odoo"
            exit -1
        fi
		display_machine_tips $2
        $dc run $2 bash
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
	telegram-setup)
		echo
		echo 1. Create a new bot and get the Token
		read -p "Now enter the token [$TELEGRAMBOTTOKEN]:" token
		if [[ -z "$token" ]]; then
			token=$TELEGRAMBOTTOKEN
		fi
		if [[ -z "$token" ]]; then

			exit 0
		fi
		echo 2. Create a new public channel, add the bot as administrator and users
		read -p "Now enter the channel name with @:" channelname
		if [[ -z "$channelname" ]]; then
			exit 0
		fi
        python $DIR/bin/telegram_msg.py "__setup__" $token $channelname
		echo "Finished - chat id is stored; bot can send to channel all the time now."
		;;
	fix-permissions)
		if [[ -d "$ODOO_FILES" && -n "$ODOO_FILES" ]]; then
			chown 1000 -R "$ODOO_FILES"
		fi
		CUSTOMS_DIR=$(
		cd $ODOO_HOME/admin/module_tools && \
		python <<-EOF
		import odoo_config
		v = odoo_config.customs_dir()
		print v
		EOF
		)
		if [[ -d "$CUSTOMS_DIR" && -n "$CUSTOMS_DIR" ]]; then
			chown 1000 -R "$CUSTOMS_DIR"
		fi

		;;
    update)
        echo "Run module update"
		if [[ -n "$ODOO_UPDATE_START_NOTIFICATION_TOUCH_FILE" ]]; then
			date +%s > $ODOO_UPDATE_START_NOTIFICATION_TOUCH_FILE
		fi
        if [[ "$RUN_POSTGRES" == "1" ]]; then
			$dc up -d postgres
        fi
        $dc kill odoo_cronjobs # to allow update of cronjobs (active cronjob, cannot update otherwise)
        $dc kill odoo_update
        $dc rm -f odoo_update
        $dc up -d postgres && sleep 3

        dcrun odoo_update /update_modules.sh $2 || {
			echo "Module Update failed"
			exit -1
		}
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
		if [[ -n "$ODOO_UPDATE_START_NOTIFICATION_TOUCH_FILE" ]]; then
			echo '0' > $ODOO_UPDATE_START_NOTIFICATION_TOUCH_FILE
		fi

       ;;

    show-openvpn-ciphers)
	   dcrun ovpn_minimal /usr/sbin/openvpn --show-ciphers
	   ;;

	enter-VPN)
		domain=$2
		machine_name="${domain}_ovpn_server_client"
		$0 up -d $machine_name
		$0 runbash $machine_name
		;;
    make-phone-CA)
		$0 make-CA asterisk
		;;
	setup-ovpn-domain)
		domain=$2

		cd $DIR/machines/openvpn
		docker_compose_file="$DIR/run/9999-docker-compose.ovpn.$domain.yml"

		cp docker-compose.yml $docker_compose_file

		;;
	force-ovpn-domain)
		domain=$2
		if [[ -z "$domain" ]]; then
			echo "OVPN Domain missing"
			exit -1
		fi
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
		domain=$2
		set -e
		$0 force-ovpn-domain $domain

        askcontinue -force
        export dc=$dc
        $dc kill ${domain}_ovpn_manage
		# backup old data before

		$(
		set -e
		mkdir -p $DIR/data/ovpn_backup
		cd $DIR/data/ovpn_backup
		if [[ -d $domain ]]; then
			tar cfz $domain-$(date +%Y%m%d-%H%M%S).tar.gz $DIR/data/ovpn/$domain
		fi
		
		)

        dcrun ${domain}_ovpn_manage clean_all.sh
        dcrun ${domain}_ovpn_manage make_ca.sh
        dcrun ${domain}_ovpn_manage make_server_keys.sh
        dcrun ${domain}_ovpn_manage make_default_keys.sh
        dcrun ${domain}_ovpn_manage pack_server_conf.sh
        ;;
    #make-keys)
        #export dc=$dc
        #bash $DIR/machines/openvpn/bin/pack.sh
        #$dc rm -f
        #;;
    export-i18n)
        LANG=$2
        MODULES=$3
        if [[ -z "$MODULES" ]]; then
            echo "Please define at least one module"
            exit -1
        fi
        dcrun odoo /export_i18n.sh $LANG $MODULES
        # file now is in $DIR/run/i18n/export.po
        ;;
    import-i18n)
        dcrun odoo /import_i18n.sh $ALL_PARAMS
        ;;
	remove-web-assets)
		askcontinue
		dcrun odoo bash -c "cd /opt/odoo/admin/module_tools; python -c'from module_tools import remove_webassets; remove_webassets()'"
		;;
	sanity_check)
		sanity_check
		;;
	make-customs)
		set -e
		askcontinue
		$0 kill
		CUSTOMS=$2
		VERSION=$3
		$ODOO_HOME/admin/module_tools/make_customs $2 $3

		$(
cd $ODOO_HOME/admin/module_tools
python <<- END
import odoo_config
env = odoo_config.get_env()
env['CUSTOMS'] = "$2"
env['DBNAME'] = "$2"
env.write()
		END
		)

		cd $ODOO_HOME/customs/$2
		git submodule add https://github.com/odoo/odoo odoo
		cd odoo
		git checkout $VERSION
		$ODOO_HOME/admin/OCA-all
		$ODOO_HOME/admin/oe-submodule tools,web_modulesroduct_modules,calendar_ics
		$ODOO_HOME/$0 up -d
		chromium-browser http://localhost

		;;
	test)
		echo 'test'
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

function try_to_set_owner() {
	OWNER=$1
	dir=$2
	if [[ "$(stat -c "%u" "$dir")" != "$OWNER" ]]; then
		echo "Trying to set correct permissions on restore directory"
		cmd="chown $OWNER $dir"
		$cmd || {
			sudo $cmd
		}
	fi
}

function sanity_check() {
    if [[ ( "$RUN_POSTGRES" == "1" || -z "$RUN_POSTGRES" ) && "$DB_HOST" != 'postgres' ]]; then
        echo "You are using the docker postgres container, but you do not have the DB_HOST set to use it."
        echo "Either configure DB_HOST to point to the docker container or turn it off by: "
        echo 
        echo "RUN_POSTGRES=0"
        exit -1
    fi

    if [[ "$RUN_POSTGRES" == "1"  ]]; then
		RESTORE_DIR="$DIR/run/restore"
		if [[ -d "$RESTORE_DIR" ]]; then
			try_to_set_owner "1000" "$RESTORE_DIR"
		fi
	fi

	if [[ -d $ODOO_FILES ]]; then
		# checking directory permissions of session files and filestorage
		try_to_set_owner "1000" "$ODOO_FILES"
	fi

	# make sure the odoo_debug.txt exists; otherwise directory is created
	if [[ ! -f "$DIR/run/odoo_debug.txt" ]]; then
		touch $DIR/run/odoo_debug.txt
	fi

	if [[ -z "ODOO_MODULE_UPDATE_DELETE_QWEB" ]]; then
		echo "Please define ODOO_MODULE_UPDATE_DELETE_QWEB"
		echo "Whenever modules are updated, then the qweb views are deleted."
		echo
		echo "Typical use for development environment."
		echo
		exit -1
	fi

	if [[ -z "ODOO_MODULE_UPDATE_RUN_TESTS" ]]; then
		echo "Please define wether to run tests on module updates"
		echo
		exit -1
	fi

	if [[ -z "$ODOO_CHANGE_POSTGRES_OWNER_TO_ODOO" ]]; then
		echo "Please define ODOO_CHANGE_POSTGRES_OWNER_TO_ODOO"
		echo In development environments it is safe to set ownership, so
		echo that accidently accessing the db fails
		echo
		exit -1
	fi
}

function set_db_ownership() {
	# in development environments it is safe to set ownership, so
	# that accidently accessing the db fails
	if [[ -n "$ODOO_CHANGE_POSTGRES_OWNER_TO_ODOO" ]]; then
		if [[ "$RUN_POSTGRES" == "1" ]]; then
			$dc up -d postgres
			dcrun odoo bash -c "cd /opt/odoo/admin/module_tools; ls; python -c'from module_tools import set_ownership_exclusive; set_ownership_exclusive()'"
		else
			bash <<-EOF
			cd $ODOO_HOME/admin/module_tools
			python -c"from module_tools import set_ownership_exclusive; set_ownership_exclusive()"
			EOF
		fi
	fi
}

function display_machine_tips() {

	tipfile=$(find $DIR/machines | grep $1/tips.txt)
	if [[ -f "$tipfile" ]]; then
		echo 
		echo Please note:
		echo ---------------
		echo
		cat $tipfile
		echo 
		echo
		sleep 1
	fi

}

function update_openvpn_domains() {

	# searches for config files of openvpn and then copies the 
	# template openvpn docker compose to run; 
	# attaches the docker-compose to $dc then

	for file in $(find $DIR/machines -name 'ovpn-domain.conf'); do
		results=$(mktemp -u)
		python $DIR/machines/openvpn/bin/prepare_domain_for_manage.py "$results" "$file" "$DIR"
		dc="$dc -f $(cat $results)"
		rm $results
	done

}

function setup_nginx_paths() {
	set -e

	URLPATH_DIR=$DIR/run/nginx_paths
	[[ -d "$URLPATH_DIR" ]] && rm -Rf $URLPATH_DIR
	mkdir -p $URLPATH_DIR
	AWK=$(which awk)

	find $DIR/machines -name 'nginx.path' | while read f; do

		cat $f | while read line; do
			URLPATH=$(echo $line | $AWK '{print $1}')
			MACHINE=$(echo $line | $AWK '{print $2}')
			PORT=$(echo $line | $AWK '{print $3}')

			if [[ -z "$PORT" || -z "$MACHINE" ]]; then
				echo "Invalid nginx urlpath: $f"
				exit -1
			fi

			$DIR/machines/nginx/add_nginx_path.sh "$URLPATH" "$MACHINE" "$PORT" "$URLPATH_DIR"
		done
	done
}

function main() {
	startup $@
	default_confs
	export_settings
	prepare_filesystem
	prepare_yml_files_from_template_files
	setup_nginx_paths
	update_openvpn_domains
	sanity_check
	export odoo_manager_started_once=1
	do_command "$@"
	cleanup

}
main $@



