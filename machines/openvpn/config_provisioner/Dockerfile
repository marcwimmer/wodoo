FROM python:3.5
MAINTAINER daniel.petermeier@conpower.de
RUN pip3 install --upgrade pip && pip3 install cherrypy
ADD ./tools/* /root/tools/
WORKDIR /root
CMD ["python3","/root/tools/monjerri.py"]


