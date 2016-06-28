FROM ubuntu:15.10
MAINTAINER marc@itewimmer.de

# Install latest git
RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive apt-get -y install python-software-properties
RUN DEBIAN_FRONTEND=noninteractive apt-get -y install software-properties-common
RUN DEBIAN_FRONTEND=noninteractive add-apt-repository ppa:git-core/ppa
RUN apt-get update

# Install some deps, lessc and less-plugin-clean-css, and wkhtmltopdf
RUN apt-get update
RUN apt-get install -y --no-install-recommends \
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
            python-support \
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
            wget

# weasy print dependencies
RUN apt-get install -y libcairo2 libpango1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info

RUN update-alternatives --install /usr/bin/node node /usr/bin/nodejs 10

# user odoo
RUN useradd -ms /bin/bash odoo

WORKDIR /
ADD sysroot/ /
RUN chown odoo:odoo /home/odoo -R


# install latest pip
RUN python /root/get-pip.py
RUN pip install --upgrade pip
RUN pip install requests[security]


# pip packages:
RUN rm -Rf /usr/local/man
RUN mkdir -p /usr/local/man/man1
ADD requirements.txt /root/requirements.txt
ADD requirements_70.txt /root/requirements_70.txt

# syntastic checker
RUN npm install -g jshint

# FIX NODE
#RUN apt-get purge 

# add ssh support for git
USER root

USER odoo
WORKDIR /home/odoo
RUN echo "git config --global credential.helper 'store [options]'" >> ~/.bashrc
RUN echo "source /opt/openerp/admin/setup_bash" >> .bash_profile
RUN echo "alias gs='git status'" >> .bash_profile

# config git environmnet
USER odoo
RUN git config --global user.name heineorange
RUN git config --global user.email heineorange
RUN git config --global http.postBuffer 1048576000
RUN git config --global push.default simple

# Adapt site customize
USER root
RUN chmod 644 /etc/python2.7/sitecustomize.py

USER root
RUN locale-gen "en_US.UTF-8"
RUN dpkg-reconfigure locales

USER root
WORKDIR /home/odoo
RUN chown odoo:odoo .ssh/authorized_keys
RUN chmod 600 .ssh/authorized_keys
RUN chmod go-rwx .ssh/*

USER root
WORKDIR /root
RUN rsync /home/odoo/.ssh/ /root/.ssh -ar
RUN chown root:root .ssh -R
RUN chmod 600 .ssh/authorized_keys
RUN chmod go-rwx .ssh/*

USER root
RUN chmod a+x /update_repos_at_start.sh
RUN chmod a+x /usr/local/bin/*

ADD run.sh /run.sh
RUN chmod a+x /run.sh

# to remember requirements installations at run.sh
VOLUME /usr/local/lib/python2.7/dist-packages

USER root
CMD /run.sh


