FROM ubuntu:16.04
ARG ODOO_VERSION
ARG ODOO_PYTHON_VERSION
ARG ODOO_EXECUTABLE
MAINTAINER marc@itewimmer.de

RUN apt-get update --fix-missing && \
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
            nodejs \
            npm \
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
            libav-tools \
            libreoffice \
            libcairo2 libpango1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info \
            locales \
            pdftk \
			libmagickwand-dev

WORKDIR /tmp

RUN update-alternatives --install /usr/bin/node node /usr/bin/nodejs 10 && \
useradd -ms /bin/bash odoo
ADD sysroot/ /
RUN \
chown odoo:odoo /home/odoo -R && \
rm -Rf /usr/local/man && mkdir -p /usr/local/man/man1

ADD requirements/$ODOO_VERSION/requirements.txt /root/requirements.txt

#install pip packages depending on version
ADD install_python_packages.sh /install_python_packages.sh

RUN chmod a+x /install_python_packages.sh
RUN /bin/bash /install_python_packages.sh "${ODOO_VERSION}" "${ODOO_PYTHON_VERSION}"

ADD bin/ /
ADD config/* /home/odoo/
RUN chmod a+x /*.sh && \
chmod 644 /etc/python2.7/sitecustomize.py && \
chmod a+x /usr/local/bin/* && \
chmod a+x /*.sh && \
chown odoo:odoo /home/odoo -R && \
locale-gen en_US.UTF-8 && \
update-locale && \
echo 'LC_ALL=en_US.UTF-8' >> /etc/environment && \
echo 'LANG=en_US.UTF-8' >> /etc/environment && \
echo 'LANGUAGE=en_US.UTF-8' >> /etc/environment 

ENV ODOO_EXECUTABLE=$ODOO_EXECUTABLE
WORKDIR /opt/odoo
