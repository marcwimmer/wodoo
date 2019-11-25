#!/bin/bash
while true;
do
	pkill -9 -f soffice.bin.*socket.*port=2002 || break
done

while true;
do
    sudo -u odoo /usr/lib/libreoffice/program/soffice.bin --headless --calc --accept="socket,host=127.0.0.1,port=2002;urp;StarOffice.ServiceManager" &
    PID=$(echo $!)
    disown $PID
    sleep 1
    kill -0 $PID  && break
done
