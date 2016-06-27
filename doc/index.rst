.. openerp productive runtime environment

odoo productinve
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
    * vim mit plugins

Verwendung
==========

Basis Verzeichnis erstellen, z.B. in Home:

    cd ~
    git clone git.mt-software.de:/git/openerp/docker/prod odoo_docker
    cd odoo_docker

Customs.env.template umkopieren und anpassen:

    cp customs.env.template customs.env
    vi customs.env

Dann die Umgebung initialisieren

    ./manage.sh init

Anschliessend Maschinen hochfahren:

    ./manage.sh upall

Einrichten eines automatischen Start-Skripts
============================================

Initial Dump einspielen
============================================

    TODO 
