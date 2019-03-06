FROM debian:stretch

# libreoffice
RUN apt-get update && \
apt install -q -y libreoffice libreoffice-writer ure libreoffice-java-common libreoffice-core libreoffice-common openjdk-8-jre fonts-opensymbol hyphen-fr hyphen-de hyphen-en-us hyphen-it hyphen-ru fonts-dejavu fonts-dejavu-core fonts-dejavu-extra fonts-droid-fallback fonts-dustin fonts-f500 fonts-fanwood fonts-freefont-ttf fonts-liberation fonts-lmodern fonts-lyx fonts-sil-gentium fonts-texgyre fonts-tlwg-purisa && \
apt -y -q remove libreoffice-gnome

WORKDIR /usr/bin
ADD loop.sh loop.sh
RUN chmod a+x loop.sh
CMD /bin/bash /usr/bin/loop.sh
