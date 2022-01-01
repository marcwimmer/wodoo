ARG BASEIMAGE=node:12.14.1-buster
ARG USER_ID
ARG VERSION
ARG DOCKER_GROUP_ID

FROM ${BASEIMAGE}
ARG USER_ID
ARG VERSION
ARG DOCKER_GROUP_ID

EXPOSE 3000
EXPOSE 3030 

LABEL mantainer="Marc Wimmer <marc@itewimmer.de>" \
    org.label-schema.build-date=$BUILD_DATE \
    org.label-schema.name="theia" \
    org.label-schema.description="Multiarch theia for amd64 arm32v7 or arm64" \
    org.label-schema.vendor="Thanks to Deft Work" \
    org.label-schema.version=$VERSION \
    org.label-schema.schema-version="1.0"

RUN adduser --disabled-password --gecos '' theia && \
    adduser theia sudo && \
    echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

WORKDIR /home/theia
ENV HOME /home/theia
RUN apt update && \
apt install -y git bash python3-pip make gcc g++ python3 libx11-dev libsecret-1-dev python-dev rsync && \
rm /usr/local/bin/yarn && rm /usr/local/bin/yarnpkg && npm install --global yarn && \
npm install -g typescript@3.5.3
ADD package.json ./package.json
RUN yarn --pure-lockfile && \
    NODE_OPTIONS="--max_old_space_size=4096" yarn theia build && \
    yarn theia download:plugins && \
    yarn --production && \
    yarn autoclean --init  && \
    echo *.ts >> .yarnclean && \
    echo *.ts.map >> .yarnclean && \
    echo *.spec.* >> .yarnclean && \
    yarn autoclean --force && \
    yarn cache clean

ENV SHELL=/bin/bash \
    THEIA_DEFAULT_PLUGINS=local-dir:/home/theia/plugins
ENV USE_LOCAL_GIT true

# customizations:
USER root

ADD git_itewimmer_readonly /root/.ssh/id_rsa
RUN chmod 400 /root/.ssh/id_rsa && \
GIT_SSH_COMMAND='ssh -i /root/.ssh/id_rsa -o IdentitiesOnly=yes -o StrictHostKeyChecking=no' git clone ssh://git@git.itewimmer.de/odoo/docker /opt/odoo 

RUN pip3 install pip -U && \
    pip3 install flake8 pylint && \
    chown theia:theia /home/theia -R && \
    chown theia:theia /home/theia/.cache -R && \
    chown theia:theia /home/theia/.config -R && \
    chown theia:theia /home/theia/.npm -R && \
    chmod 770 /home/theia/.config  && \
    chown theia:theia /home/theia/plugins -R && \
    echo '#!/bin/bash\n/opt/odoo/odoo "$@"' > /usr/local/bin/odoo && \
    chmod a+x /usr/local/bin/odoo && \
    apt install -y fzf docker.io && \
    mkdir -p /home/theia/.theia/globalStorage/vscodevim.vim && \
    touch /home/theia/.theia/globalStorage/vscodevim.vim/.registers && \
    chown theia:theia /home/theia/.theia -R && \
    chown theia:theia /home/theia -R && \
    addgroup --gid $DOCKER_GROUP_ID docker_host && \
    usermod -aG docker_host theia && \
    mkdir -p /home/theia/.cache/pip && \
    chown theia:theia /home/theia/.cache -R && \
    pip3 install -r /opt/odoo/requirements.txt && \
    pip3 install flake8 pylint 

ADD entrypoint.sh /entrypoint.sh
RUN chmod a+rwx /entrypoint.sh
USER theia
ENTRYPOINT [ "/entrypoint.sh" ]
