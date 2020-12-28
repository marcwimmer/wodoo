FROM python:3.8-buster
WORKDIR /usr/src/app

COPY app/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

ADD app/ ./

CMD [ "python", "./run.py", "--port=80"]
