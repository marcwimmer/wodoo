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
