FROM python:2
WORKDIR /usr/src
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY bin/debug.sh /
RUN chmod a+x /debug.sh
ADD bin/debug.sh /usr/local/bin
CMD ["python", "connector.py"]
