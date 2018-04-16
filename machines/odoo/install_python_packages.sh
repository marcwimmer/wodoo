#!/bin/bash
set -e
set -x
ODOO_VERSION="$1"
ODOO_PYTHON_VERSION="$2"

[[ "$VERBOSE" == "1" ]] && set -x

echo "Installing python for odoo"

if [[ "$ODOO_PYTHON_VERSION" == "2" ]]; then
	apt install -y \
		libpython-dev \
		python \
		python-software-properties \
		python-pip \
		python-pyinotify \
		python-renderpm \
		python-dev \
		python-lxml \
		python-pychart \
		python-gevent \
		python-ldap \
		python-cups \
		python-psycopg2 \
		python-wand  \
		python-magic
	PIP=pip
	$PIP install requests[security]
	$PIP install glob2

elif [ "$ODOO_PYTHON_VERSION" == "3" ]; then 
	
	# minimum python for admin scripts;
	apt install -y python python-pip python-psycopg2 python-lxml
	pip install unidecode

	apt install -y \
		python3-dev \
		python3-pip \
		python3 \
		python3-pyinotify  \
		python3-renderpm \
		python3-magic \
		python3-wand \
		python3-cups \
		python3-psycopg2
	PIP=pip3

fi

$PIP install pip==9.0.3 --upgrade

# minimum packages
$PIP install pudb
$PIP install -r /root/requirements.txt

#7.0
case "$ODOO_VERSION" in
	"6.0" | "6.1" | "7.0")
		echo ''
	;;
	*)
		echo "Installing version $1 requirements"
		wget https://raw.githubusercontent.com/odoo/odoo/$ODOO_VERSION/requirements.txt -O /root/requirements_$ODOO_VERSION.txt
		$PIP install -r /root/requirements_$1.txt
	;;

esac

set +x
