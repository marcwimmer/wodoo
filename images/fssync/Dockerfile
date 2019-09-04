FROM debian:buster
RUN apt update
RUN apt install -y rsync watch python3 python3-pip
RUN apt install -y ocaml-nox
ADD https://github.com/bcpierce00/unison/archive/v2.51.2.tar.gz /root/unison.tar.gz
WORKDIR /root/
RUN tar xfz unison.tar.gz
RUN cd unison-2.51.2
WORKDIR /root/unison-2.51.2
RUN make -j4 UISTYLE=text
RUN cp src/unison /usr/bin/unison
RUN useradd unison -d /home/unison
RUN mkdir /home/unison
RUN chown unison:unison /home/unison
ADD run.sh /
RUN chmod a+x /run.sh
