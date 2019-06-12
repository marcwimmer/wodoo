FROM debian:stretch
WORKDIR /usr/bin

# libreoffice
RUN apt-get update && \
apt install -q -y libreoffice libreoffice-writer ure libreoffice-java-common libreoffice-core libreoffice-common openjdk-8-jre fonts-opensymbol hyphen-fr hyphen-de hyphen-en-us hyphen-it hyphen-ru fonts-dejavu fonts-dejavu-core fonts-dejavu-extra fonts-droid-fallback fonts-dustin fonts-f500 fonts-fanwood fonts-freefont-ttf fonts-liberation fonts-lmodern fonts-lyx fonts-sil-gentium fonts-texgyre fonts-tlwg-purisa && \
apt -y -q remove libreoffice-gnome python


ADD loop.py loop.py
CMD /usr/bin/python /usr/bin/loop.py
