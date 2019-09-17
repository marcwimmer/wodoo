FROM debian:buster
RUN apt update && apt install -y python3-pip python3
ADD requirements.txt
RUN pip3 install -r requirements.txt
WORKDIR /opt/odoo

