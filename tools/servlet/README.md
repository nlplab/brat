# brat servlet #

This is a full-fledged brat CGI servlet to deploy brat on Tomcat. While this
is a bit of an exotic usecase, it is an existing one and this README along
with XML provided should keep you from crying your eyes out while solving this
exercise.

# Building #

First, some words on how this works. You will attempt a WAR (Web application
ARchive) containing a working brat installation. This means you will first
have to install brat as usual and deploy your data. Deploy your brat
installation in `brat/WEB-INF/cgi`, then, proving that you don't need ant to
build something Java-ish, simply run:

    make

This will produce a file `brat.war` that you can deploy on Tomcat.

# Installation #

Drop the `brat.war` into the Tomcat `webapps` directory and you should be able
to access your installation using:

    http://${HOSTNAME}:${PORT}/brat/

From now on, brat should work as usual with the exception that it is Tomcat
serving your requests.
