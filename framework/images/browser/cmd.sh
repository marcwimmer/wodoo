#!/bin/bash

echo "$PASSWORD" | vncpasswd -f > .vnc/passwd
chmod o-rwx,g-rwx .vnc/passwd
vncserver :1 -geometry "$GEOMETRY" -depth "$DEPTH"
while true;
do
    sleep 100
done
