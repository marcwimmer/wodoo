FROM node:16-buster
ARG USER_ID
RUN npm install -g yo @theia/generator-plugin
USER root
RUN usermod -u $USER_ID node
USER node
WORKDIR /out