#!/bin/bash
set -e
set -x
source /eval_odoo_settings.sh

[[ "$VERBOSE" == "1" ]] && set -x

echo "Installing python for odoo"

if [[ "$ODOO_PYTHON_VERSION" == "2" ]]; then
	apt install -y \
		libpython-dev \
		python \
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
	$PIP install pip==9.0.3 --upgrade

elif [ "$ODOO_PYTHON_VERSION" == "3" ]; then 
	
	# minimum python for admin scripts;
	apt install -y python python-pip python-psycopg2 python-lxml
    apt install -y python3-gi python3-click python3-gi-cairo python3-cairo gir1.2-gtk-3.0
	pip install unidecode pudb
	pip install pip --upgrade

	hash -r
	pip install pip --upgrade;
	apt install -y python3-pip python3-dev python3 
	hash -r  # pip3 10.0 is in other directories; hash -r clears the cache of the path
	pip install --upgrade pip
	hash -r
	apt remove -y python3-pip
	easy_install3 pip
	hash -r
	pip3 install --upgrade setuptools

	pip3 install psycopg2
	pip3 install pyinotify

	apt install -y libmagickwand-dev libmagic-dev
	pip3 install python-magic
	pip3 install wand

	apt install -y libcups2-dev
	pip3 install pycups
	PIP=pip3

else
    exit 1
fi


# minimum packages
hash -r
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
		$PIP install -r /root/requirements_$ODOO_VERSION.txt
	;;

esac

set +x
