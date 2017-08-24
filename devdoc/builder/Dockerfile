FROM ubuntu:15.10
MAINTAINER Marc Wimmer
ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update -q
RUN apt-get install -qy texlive-full 
RUN apt-get install -qy python-pygments 
RUN apt-get install -qy gnuplot
RUN apt-get install -qy python-pip 
RUN apt-get install -qy graphviz
RUN pip install pip --upgrade
RUN pip install Sphinx sphinxcontrib-tikz
RUN apt-get install -y python-pillow
RUN apt-get install -y librsvg2-bin plotutils graphviz
RUN pip install sphinx-scruffy
ADD run.sh /run.sh
RUN chmod a+x /run.sh

WORKDIR /data
VOLUME ["/in", "/out"]
CMD /run.sh
