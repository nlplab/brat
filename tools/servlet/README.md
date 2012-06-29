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

CGI is disabled in Tomcat by default (understandable), so you'll need to
configure your Tomcat instance before it will succesful run your newly created
`brat.war`.

Find the `web.xml` for your Tomcat installation and uncomment the two CGI
sections that should look something like:

    <servlet>
        <servlet-name>cgi</servlet-name>
        <servlet-class>org.apache.catalina.servlets.CGIServlet</servlet-class>
        <init-param>
            <param-name>debug</param-name>
            <param-value>0</param-value>
        </init-param>
        <init-param>
            <param-name>cgiPathPrefix</param-name>
            <param-value>WEB-INF/cgi</param-value>
        </init-param>
        <load-on-startup>5</load-on-startup>
    </servlet>

And:

    <servlet-mapping>
        <servlet-name>cgi</servlet-name>
        <url-pattern>/cgi-bin/*</url-pattern>
    </servlet-mapping>

Then drop the `brat.war` into the Tomcat `webapps` directory and you should be
able to access your installation using:

    http://${HOSTNAME}:${PORT}/brat/XXX

From now on, brat should work as usual with the exception that it is Tomcat
serving your requests.

# TODO #

* Can we remap URL;s so that we don't have to do the stupid cgi-bin in the URL?
* Also, can we somehow place the index.html somewhere useful so that we can do
    more than just serving the CGI?
* Fix the example URL to the installation
