EINLEITUNG
===============

In diesem Repo befinden sich Tools, um odoo mit einem asterisk-server
per MQTT zu verbinden.
Ausserdem sind Beschreibungen vorhanden, um einen Test-Asterisk per Docker
aufzusetzen.


Module
==============

Module sind eigenstaendig zu sehen, damit diese ggf. auf einer 
eigenen Freepbx-Maschine losgeloest von odoo installiert werden koennen.


connector_mqtt_ariami
------------------------------------

- ARI/AMI Interface zu MQTT: sends channels events via mqtt and starts calls triggered by mqtt

Anpassungen notwendig zur Funktion:
- AMI Interface:
  - User admin benoetigt permit des Docker-Netzwerks:
    manager_custom.conf
    [admin]
    permit=172.18.0.2/255.255.255.0

connector_mqtt_freepbxdb
--------------------------------------
- MQTT Interface zur freepbx mysql datenbank manipulation


Aufsetzen eines Test-Asterisks
============================================
Beachte README in ./docker
