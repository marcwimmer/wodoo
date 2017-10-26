FROM ubuntu:16.04
RUN apt update && apt install -y python-pip
RUN pip install python-telegram-bot
ADD setup.sh /setup.sh
ADD send.sh /send.sh
CMD echo "Plz use setup.sh and send.sh"
