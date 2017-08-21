.. openerp suite

odoo suite
==================================

Vorwort
==================

Produktionsmaschinen für odoo.

Minimal:
    * odoo server
    * postgres server

Optional:
    * Asterisk Server
    * Asterisk ARI Connector
    * Radicale Server
    * Mail Server
    * ...

Verwendung
==========

Basis Verzeichnis erstellen, z.B. in Home:

    cd ~
    git clone git.mt-software.de:/git/openerp/docker/prod odoo
    cd odoo

Settings anpassen:

    cp ./settings.template/settings settings
    vi settings

Dann die Umgebung initialisieren

    ./manage.sh build

Anschliessend Maschinen hochfahren:

    ./manage.sh up -d

Einrichten eines automatischen Start-Skripts
============================================

  ./manage.sh setup-startup

Initial Dump einspielen
============================================

  ./manage.sh restore DUMP.gz FILES.tar
