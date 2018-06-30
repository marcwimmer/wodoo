#!/bin/bash
chown root /root/.vnc -R

echo "$PASSWORD" | vncpasswd -f > /root/.vnc/passwd
chmod o-rwx,g-rwx /root/.vnc/passwd
vncserver :1 -geometry 1440x960 -depth 24
while true;
do
    sleep 100
done
