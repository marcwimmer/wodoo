FROM ubuntu:20.04
WORKDIR /code
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -
RUN add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu focal stable"
RUN apt update && DEBIAN_FRONTEND="noninteractive" apt install -y python3-pip apt-transport-https ca-certificates curl gnupg2 software-properties-common docker-ce

COPY requirements.txt requirements.txt


RUN pip3 install -r requirements.txt
EXPOSE 5000
COPY . .
CMD ["flask", "run"]
