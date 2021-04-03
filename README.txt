/usr/local/bin/odoo:

#!/bin/bash
source /opt/odoo/.venv/bin/activate && /opt/odoo/odoo "$@"


Setup a new odoo:

    odoo init


Setup as jenkins job for anonymizing database:

    git clone odoo src
    cd src
    odoo reload --local --devmode --headless --project-name 'unique_name'
    odoo cicd register
    odoo down -v
    odoo -f db reset

Setup to be part of cicd framework:

    odoo cicd register <branch-name>




How to extend an existing service:
------------------------------------

Provide a local docker-compose file.

services:
  odoo3:
    labels:
      compose.merge: base-machine
    

Example for fixed ip addresses:
---------------------------------
services:     
    proxy:    
        networks:    
            network1:    
                ipv4_address: 10.5.0.6    
networks:    
    network1:    
        driver: bridge    
        ipam:    
            config:    
                - subnet: 10.5.0.0/16



Useful links:
----------------------------
  * UFW and Docker: https://github.com/chaifeng/ufw-docker
