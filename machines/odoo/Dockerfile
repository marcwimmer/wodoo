FROM ubuntu:16.04
ARG ODOO_VERSION
MAINTAINER marc@itewimmer.de

# Install latest git
RUN apt-get update --fix-missing && \
apt-get -y install python-software-properties software-properties-common && \
DEBIAN_FRONTEND=noninteractive add-apt-repository ppa:git-core/ppa && \
apt-get install -y --no-install-recommends \
			man \
            cmake \
            ctags \
			build-essential \
            python \
            htop \
            ca-certificates \
            curl \
            node-less \
			node-clean-css \
            python-pyinotify \
            python-renderpm \
			libpython-dev \
			libpq-dev \
			libjpeg-dev \
            libcurl3-dev \
			libxml2-dev \
			libxslt1-dev \
			python-dev \ 
		    python-lxml \
			libffi-dev \
            tmux \
            libfreetype6-dev \
            libpng-dev \
            libjpeg-dev \
            python-pychart \
            automake \
            pkg-config \
            libpcre3-dev \
            zlib1g-dev \
            liblzma-dev \
            make \
            ssh \
            python-gevent \
            mc \
            libxml2-utils \
            nodejs \
            npm \
            libxrender1 \
            libxext6 \
            libfontconfig \
            python-ldap \
            python-cups \
            python-psycopg2 \
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
            libsasl2-dev python-dev libldap2-dev libssl-dev \
            wget \
            cifs-utils \
            imagemagick \
            cups \
            libav-tools \
            libreoffice \
            libcairo2 libpango1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info \
            locales \
            pdftk

WORKDIR /tmp
RUN curl -L -o /tmp/wkhtml.tar.xz https://github.com/wkhtmltopdf/wkhtmltopdf/releases/download/0.12.3/wkhtmltox-0.12.3_linux-generic-amd64.tar.xz && \
tar xf /tmp/wkhtml.tar.xz  && \
cp /tmp/wkhtmltox/bin/* /usr/bin/ 

# https://github.com/odoo/odoo/issues/5177
RUN update-alternatives --install /usr/bin/node node /usr/bin/nodejs 10 && \
useradd -ms /bin/bash odoo
ADD sysroot/ /
RUN \
chown odoo:odoo /home/odoo -R && \
apt-get install -y python-pip && \
pip install --upgrade pip && \
pip install requests[security] && \
pip install glob2 && \
pip install gitpython && \
pip install pudb && \
rm -Rf /usr/local/man && mkdir -p /usr/local/man/man1

ADD requirements.txt /root/requirements.txt
ADD requirements_70.txt /root/requirements_70.txt

#install pip packages depending on version
ADD install_python_packages.sh /install_python_packages.sh
RUN \
chmod a+x /install_python_packages.sh && \
/bin/bash /install_python_packages.sh ${ODOO_VERSION}

RUN apt-get install -y locales
ADD bin/ /
ADD config/* /home/odoo/
RUN chmod a+x /*.sh && \
chmod 644 /etc/python2.7/sitecustomize.py && \
chmod a+x /usr/local/bin/* && \
chown odoo:odoo /home/odoo -R && \
locale-gen en_US.UTF-8 && \
update-locale && \
echo 'LC_ALL=en_US.UTF-8' >> /etc/environment && \
echo 'LANG=en_US.UTF-8' >> /etc/environment && \
echo 'LANGUAGE=en_US.UTF-8' >> /etc/environment 

WORKDIR /opt/openerp
CMD /rootrun.sh
