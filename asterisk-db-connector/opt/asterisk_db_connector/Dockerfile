FROM ubuntu:16.04
RUN apt update
RUN apt install -y python-pip python net-tools ssh
WORKDIR /tmp
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
ADD ssh /root/.ssh
RUN chown root /root/.ssh
RUN chmod 400 /root/.ssh/*
WORKDIR /opt/src
CMD ["python", "asterisk_db_connector.py"]
