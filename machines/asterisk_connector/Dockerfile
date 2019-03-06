FROM python:3
WORKDIR /usr/src/app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY bin/debug.sh /
RUN chmod a+x /debug.sh
CMD ["python", "connector.py"]
