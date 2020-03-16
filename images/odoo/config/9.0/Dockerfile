FROM ubuntu:18.04
ARG ODOO_VERSION
MAINTAINER marc@itewimmer.de

RUN apt update --fix-missing && \
apt-get install \
	-y \
	--no-install-recommends \
			software-properties-common \
			man \
            cmake \
            ctags \
			build-essential \
            htop \
            ca-certificates \
            curl \
            node-less \
			node-clean-css \
			libpq-dev \
			libjpeg-dev \
            libcurl3-dev \
			libxml2-dev \
			libxslt1-dev \
			libffi-dev \
            tmux \
            libfreetype6-dev \
            libpng-dev \
            libjpeg-dev \
            automake \
            pkg-config \
            libpcre3-dev \
            zlib1g-dev \
            liblzma-dev \
            make \
            ssh \
            mc \
            libxml2-utils \
            libxrender1 \
            libxext6 \
            libfontconfig \
            htop \
            rsync \
            vim \
            psmisc \
            lsof \
            git \
            tig \
            sudo \
            less \
            freetds-dev \
            libsasl2-dev \
			libldap2-dev \
			libssl-dev \
            wget \
            cifs-utils \
            imagemagick \
            cups \
            libreoffice \
            libcairo2 libpango1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info \
            locales \
			libmagickwand-dev \
            ffmpeg \
            zip \
            gpg-agent \
            python3-pip \
            python3-setuptools \
            python3-dev

RUN \
sudo add-apt-repository ppa:malteworld/ppa && \
sudo apt update && \
sudo apt install -y pdftk

ADD liberation-sans /usr/share/fonts/
# rebuild font cache
RUN fc-cache -f -v


# Install nodejs and npm
RUN \
curl -sL https://deb.nodesource.com/setup_10.x | sudo -E bash - && \
curl -sL https://dl.yarnpkg.com/debian/pubkey.gpg | sudo apt-key add -  && \
apt update && apt install -y nodejs yarn 

RUN \
locale-gen en_US.UTF-8 && \
update-locale && \
echo 'LC_ALL=en_US.UTF-8' >> /etc/environment && \
echo 'LANG=en_US.UTF-8' >> /etc/environment && \
echo 'LANGUAGE=en_US.UTF-8' >> /etc/environment 

# libreoffice
#RUN apt-get update && \
#apt install -q -y libreoffice libreoffice-writer ure libreoffice-java-common libreoffice-core libreoffice-common openjdk-8-jre fonts-opensymbol hyphen-fr hyphen-de hyphen-en-us hyphen-it hyphen-ru fonts-dejavu fonts-dejavu-core fonts-dejavu-extra fonts-droid-fallback fonts-dustin fonts-f500 fonts-fanwood fonts-freefont-ttf fonts-liberation fonts-lmodern fonts-lyx fonts-sil-gentium fonts-texgyre fonts-tlwg-purisa && \
#apt -y -q remove libreoffice-gnome

WORKDIR /tmp

RUN curl -o wkhtmltox.tar.xz -SL https://github.com/wkhtmltopdf/wkhtmltopdf/releases/download/0.12.4/wkhtmltox-0.12.4_linux-generic-amd64.tar.xz \
        && echo '3f923f425d345940089e44c1466f6408b9619562 wkhtmltox.tar.xz' | sha1sum -c - \
        && tar xvf wkhtmltox.tar.xz \
        && cp wkhtmltox/lib/* /usr/local/lib/ \
        && cp wkhtmltox/bin/* /usr/local/bin/ \
        && cp -r wkhtmltox/share/man/man1 /usr/local/share/man/


RUN update-alternatives --install /usr/bin/node node /usr/bin/nodejs 10 && \
useradd -ms /bin/bash odoo
ADD sysroot/ /
RUN \
chown odoo:odoo /home/odoo -R && \
rm -Rf /usr/local/man && mkdir -p /usr/local/man/man1

RUN apt install -y \
		libpython-dev \
		python \
		python-pip \
		python-pyinotify \
		python-renderpm \
		python-dev \
		python-lxml \
		python-pychart \
		python-gevent \
		python-ldap \
		python-cups \
		python-psycopg2 \
		python-wand  \
		python-magic && \
	pip install requests[security] && \
	pip install glob2 && \
	pip install pip==9.0.3 --upgrade
RUN pip3 install lxml psycopg2-binary click pudb psutil

ADD https://raw.githubusercontent.com/odoo/odoo/${ODOO_VERSION}/requirements.txt /root/odoo_requirements.txt
ADD config/$ODOO_VERSION/requirements.txt /root/requirements.txt
RUN pip install pathlib2
RUN pip install -r /root/requirements.txt
RUN pip install -r /root/odoo_requirements.txt

# python2 binary error on ubuntu 18.04
# https://github.com/psycopg/psycopg2-wheels/issues/2
RUN mv /bin/sh /bin/sh.bak; ln -s /bin/bash /bin/sh
RUN pip uninstall -y psycopg2
RUN pip install --no-binary psycopg2
RUN rm /bin/sh; mv /bin/sh.bak /bin/sh

WORKDIR /opt

RUN pip3 install humanize retrying click pyyaml requests passlib arrow inquirer tabulate
