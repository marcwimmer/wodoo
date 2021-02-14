FROM ubuntu:20.04
RUN apt-get update && apt-get install -y python3.8 python3-pip
RUN pip3 install webssh
EXPOSE 8080
CMD ["wssh", "--address=0.0.0.0", "--port=8080"]
