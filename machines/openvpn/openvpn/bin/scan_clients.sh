#!/bin/bash

while true;
do
    echo "Showing active clients (asterisk server + phones)"
    nmap 10.28.0.0/16 -n -sP | grep report | awk '{print $5}'
    sleep 15
done
