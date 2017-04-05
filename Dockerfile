FROM ubuntu:16.04

RUN apt-get update && apt-get install -y python2.7-dev build-essential automake libpcre3 libpcre3-dev
RUN apt-get update && apt-get install -y wget vim python

WORKDIR /app/brat/swig
RUN wget http://prdownloads.sourceforge.net/swig/swig-3.0.12.tar.gz
RUN tar xzf swig-3.0.12.tar.gz
RUN cd swig-3.0.12 && ./autogen.sh && ./configure
RUN cd swig-3.0.12 && make && make install

ADD simstring /app/brat/simstring

WORKDIR /app/brat/simstring
RUN ./autogen.sh && ./configure
RUN make && make install

RUN cd swig/python && ./prepare.sh --swig && python setup.py install 
RUN cd swig/python && python sample.py

ADD . /app/brat

WORKDIR /app/brat

CMD python standalone.py

