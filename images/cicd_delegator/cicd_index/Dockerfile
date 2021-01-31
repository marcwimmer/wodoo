FROM ubuntu:20.04
WORKDIR /code
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
RUN apt update && apt install -y python3-pip
RUN DEBIAN_FRONTEND="noninteractive" apt -y install apt-transport-https ca-certificates curl gnupg2 software-properties-common
#RUN curl -fsSL https://download.docker.com/linux/debian/gpg | apt-key add -
# RUN add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/debian $(lsb_release -cs) stable"
RUN apt install -y docker-ce

COPY requirements.txt requirements.txt


RUN pip3 install -r requirements.txt
EXPOSE 5000
COPY . .
CMD ["flask", "run"]
