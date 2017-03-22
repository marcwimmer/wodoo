#!/bin/bash
./manage.sh kill odoo
./manage.sh kill nginx
./manage.sh up -d
