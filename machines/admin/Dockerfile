FROM ubuntu:16.04
ENV ODOO_VERSION=10.0
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
            libsasl2-dev python-dev libldap2-dev libssl-dev \
            cifs-utils \
            libav-tools \
            libcairo2 libpango1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info \
            locales \
            pdftk \
			gosu \
			wget \
			postgresql \
			gettext-base \
			python-pip \
			locales \
			python-setuptools


# install docker cli
RUN curl https://download.docker.com/linux/static/stable/x86_64/docker-17.03.2-ce.tgz -o /tmp/docker.tgz
RUN mkdir -p /opt/docker
WORKDIR /opt/docker
RUN tar xfz /tmp/docker.tgz
WORKDIR /

#install pip packages depending on version
RUN pip install pip --upgrade
ADD bin/install_python_packages.sh /install_python_packages.sh
RUN chmod a+x /install_python_packages.sh
RUN /bin/bash /install_python_packages.sh ${ODOO_VERSION}


ADD init.sql /tmp/init.sql
RUN update-alternatives --install /usr/bin/node node /usr/bin/nodejs 10 && \
useradd -ms /bin/bash odoo
ADD sysroot/ /
RUN \
chown odoo:odoo /home/odoo -R && \
rm -Rf /usr/local/man && mkdir -p /usr/local/man/man1

ADD requirements.txt /tmp
RUN pip install -r /tmp/requirements.txt

ADD ssh/ /home/odoo/.ssh/
RUN \
chown odoo:odoo /home/odoo/.ssh -R && \
chmod a-rwx -R /home/odoo/.ssh && \
chmod u+rw -R /home/odoo/.ssh && \
chmod u+x /home/odoo/.ssh

ADD bin/ /
ADD config/* /opt
RUN chmod a+x /*.sh && \
chmod 644 /etc/python2.7/sitecustomize.py && \
chmod a+x /usr/local/bin/* && \
chown odoo:odoo /home/odoo -R && \
locale-gen en_US.UTF-8 && \
update-locale && \
echo 'LC_ALL=en_US.UTF-8' >> /etc/environment && \
echo 'LANG=en_US.UTF-8' >> /etc/environment && \
echo 'LANGUAGE=en_US.UTF-8' >> /etc/environment 


CMD /run.sh
