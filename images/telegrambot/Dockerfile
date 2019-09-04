FROM ubuntu:16.04
RUN apt update && apt install -y python-pip
RUN pip install python-telegram-bot
ADD setup.sh /setup.sh
ADD send.py /send.py
RUN chmod a+x /setup.sh /send.py
CMD echo "Plz use setup.sh and send.sh"
