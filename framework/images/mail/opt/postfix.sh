#!/bin/bash
set -ex
service postfix start
tail -f /var/log/mail.log
