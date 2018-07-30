Anpassungen notwendig zur Funktion:
- AMI Interface: test

  - User admin benoetigt permit des Docker-Netzwerks:

manager_custom.conf
[admin]
permit=172.18.0.2/255.255.255.0


asterisk-connector
- ARI/AMI Interface zu MQTT
- Build Asterisk_ari_connector docker
- start asterisk_ari_connector docker

asterisk-db-connector
- MQTT Interface zur asterisk datenbank manipulation
- Aktuell keine Dockerversion da direkt Zugriff auf Datenbank nicht konfiguriert wurde
- DockerFiles wurden erstellt aber noch nicht verwendet.
- Autostart mit Services für Ubuntu 14.04 und neuer.

- Installation:
- dpkg -i asterisk-db-connector_1_3_2.deb
- Installiert die Files:
- /etc/init/asterisk-db-connector.conf
- /etc/init/systemd/system/asterisk_db_connector.service
- /opt/asterisk_db_connector/src/asterisk_db_connector.py
- /opt/asterisk_db_connector/src/fpbxconnector.py

asterisk_db_connector.py:
	Meldet sich in MQTT an, reicht Messages an FPBXConnector Klasse weiter.

fpbxdb_connector.py:
	Enthält die Funktionalitäten zum Zugriff und zur Manipulation der Datenbank.
	Gibt das Ergebnis für asterisk_db_connector.py optimiert zurück.

starten der Applikation:
	sudo service asterisk_db_connector start

