# brat servlet #

This is a full-fledged brat CGI servlet to deploy brat on Tomcat. While this
is a bit of an exotic usecase, it is an existing one and this README along
with the XML provided should keep you from crying your eyes out while solving
this exercise.

# Building #

First, some words on how this works. You will attempt to create a WAR (Web
application ARchive) containing a working brat installation. This means you
will first have to install brat as usual and deploy your data. Create the brat
folder structure as shown (`brat/WEB-INF`, `brat/META-INF`) with the given
`web.xml` and `context.xml`. Copy your previously installed brat installation
to `brat/`, then, proving that you don't need ant to build something Java-ish,
simply go to the parent folder of `brat`, where the `GNUmakefile` is, and run:

    make

This will produce an archive `brat.war` that you can deploy on Tomcat.

# Installation #

Drop the `brat.war` into the Tomcat `webapps` directory and you should be able
to access your installation using:

    http://${HOSTNAME}:${PORT}/brat/

From now on, brat should work as usual with the exception that it is Tomcat
serving your requests.
