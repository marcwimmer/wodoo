#
# Chrome Dockerfile
#
# https://github.com/dockerfile/chrome
#

# Pull base image.
FROM ubuntu:18.04

ENV DEBIAN_FRONTEND noninteractive

# Install Chromium.
RUN \
  apt-get update -y && \
  apt-get install -y apt-utils wget openssh-server \
  gconf-service libnspr4 libnss3 fonts-liberation \
  libappindicator1 libcurl3 fonts-wqy-microhei tightvncserver 
RUN apt install -y gnupg2
RUN \
  wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
  echo "deb http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google.list
RUN \
  apt-get update -y && \
  apt-get install -y google-chrome-stable 

RUN \
  groupadd -g 1000 user1 && \
  useradd -u 1000 -g 1000 -m -d /data user1 

RUN \
  mkdir -p /var/run/sshd && \
  sed -ri 's/UsePAM yes/#UsePAM yes/g' /etc/ssh/sshd_config && \
  sed -ri 's/#Port 22/Port 5800/g' /etc/ssh/sshd_config 

#RUN apt install -y xfce4 xfce4-goodies x11vnc xvfb
RUN apt install -y fluxbox


#RUN rm -rf /var/lib/apt/lists/* 

WORKDIR /data

# password is odoo2000
RUN mkdir .vnc
ADD vncconfig/ .vnc/
ADD fluxbox/ .fluxbox/
ADD cmd.sh cmd.sh
ENV USER=user1

# Define default command.
RUN \
chmod a+x cmd.sh && \
chmod a+x .vnc/xstartup && \
chown user1 . -R

USER user1
CMD ./cmd.sh
