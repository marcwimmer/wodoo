FROM ubuntu:20.04

# wget
RUN export DEBIAN_FRONTEND=noninteractive
RUN apt update -q 
RUN apt install -y tzdata wget unzip python3
RUN apt install -y python3-pip python3-magic libmagickwand-dev xvfb

# chrome for testing
RUN wget -O /tmp/google-chrome-stable_current_amd64.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update -qq \
    && apt-get install -y /tmp/google-chrome-stable_current_amd64.deb \
    && rm -rf /tmp/google-chrome-stable_current_amd64.deb

RUN wget -O /tmp/chromedriver_linux64.zip http://chromedriver.storage.googleapis.com/2.40/chromedriver_linux64.zip \
    && unzip /tmp/chromedriver_linux64.zip -d /opt/chromedriver \
    && chmod +x /opt/chromedriver/chromedriver \
    && ln -fs /opt/chromedriver/chromedriver /usr/local/bin/chromedriver \
    && rm -rf /tmp/chromedriver_linux64.zip


COPY ./requirements.txt /tmp/requirements.txt
RUN \
pip3 install --no-cache-dir -r /tmp/requirements.txt && \
rm -rf /tmp/requirements.txt

ENV WORKDIR=/opt/robot
WORKDIR $WORKDIR
COPY robotest.py robotest.sh ./
CMD [ "python3", "robotest.py"]
