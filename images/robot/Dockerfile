FROM ubuntu:20.04

# wget
RUN export DEBIAN_FRONTEND=noninteractive
RUN apt update -q 
RUN apt install -y tzdata wget unzip python3
RUN apt install -y python3-pip python3-magic libmagickwand-dev xvfb

# chrome for testing
RUN apt install -y chromium-browser

COPY ./requirements.txt /tmp/requirements.txt
RUN \
pip3 install --no-cache-dir -r /tmp/requirements.txt && \
rm -rf /tmp/requirements.txt

RUN if [ "$(dpkg --print-architecture)" = "amd64" ]; then \
wget -O /tmp/chromedriver_linux64.zip https://chromedriver.storage.googleapis.com/91.0.4472.19/chromedriver_linux64.zip; \
fi

RUN if [ "$(dpkg --print-architecture)" = "arm64" ]; then \
wget -O /tmp/chromedriver_linux64.zip https://github.com/electron/electron/releases/download/v14.0.0-beta.1/chromedriver-v14.0.0-beta.1-linux-arm64.zip; \
fi

RUN unzip /tmp/chromedriver_linux64.zip -d /opt/chromedriver \
    && chmod +x /opt/chromedriver/chromedriver \
    && ln -fs /opt/chromedriver/chromedriver /usr/local/bin/chromedriver \
    && rm -rf /tmp/chromedriver_linux64.zip

ENV WORKDIR=/opt/robot
WORKDIR $WORKDIR
COPY robotest.py ./
CMD [ "python3", "robotest.py"]
