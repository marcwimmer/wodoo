FROM ubuntu:20.04
CMD [ "bash", "/root/launch.sh" ]
RUN apt update && \
    apt -y upgrade && \
    apt install -y --no-install-recommends \
    nginx  procps \
    python3-pip \
    python3 \
    python3-setuptools \
    ssh \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg-agent \
    software-properties-common
RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add - && \
add-apt-repository \
   "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
   $(lsb_release -cs) \
   stable" && \
   apt-get update && \
   apt-get install -y docker-ce docker-ce-cli containerd.io
RUN apt-get update && apt-get install -y python3.8 python3-pip && pip3 install webssh
ADD nginx /etc/nginx/sites-enabled/default
RUN nginx -c /etc/nginx/nginx.conf -t
ADD launch.sh /root
RUN chmod a+x /root/launch.sh
# RUN useradd -ms /bin/bash console
RUN echo "root:odoo" | chpasswd root
RUN sed -i 's/\#PermitRootLogin\ prohibit-password/PermitRootLogin yes/g' /etc/ssh/sshd_config 
RUN cat /etc/ssh/sshd_config |grep Permit
