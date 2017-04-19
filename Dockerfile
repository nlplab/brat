FROM ubuntu:16.04

RUN apt-get update && apt-get install -y python2.7-dev build-essential automake libpcre3 libpcre3-dev python-pip python-dev
RUN apt-get update && apt-get install -y wget vim python
RUN pip install config

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

#RUN ./install.sh
CMD python tools/norm_db_init.py example-data/normalisation/Wiki.txt

CMD python standalone.py

# To debug the configurations and/or install missing libraries,
# use the following command instead of `CMD python standalone.py`:
#CMD bash
