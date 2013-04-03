---
# -*- Mode: Markdown; tab-width: 4; indent-tabs-mode: nil; -*-
# vim:set ft=markdown ts=4 sw=4 sts=4 autoindent:

layout: base
title:  "Installation"
cmeta:  "Instructions on how to install brat on your system."
---
# brat installation #

This page describes how to install a brat server and its third-party
dependencies.

<p style="color:gray">
    (If you already have a running server, you may wish to read about
    <a href="configuration.html">annotation configuration</a> next.)
</p>

**Please note**: you do not need to install brat to try it out;
brat runs in your browser and a live demo system usable with any
[supported browser](supported-browsers.html) is
linked form the [brat home page](index.html).

If you wish to set up your own local brat installation for your
annotation project, please follow the instructions below.

## Table of contents ##

<ul>
<li><a href="#quick_start">Quick start</a></li>
<li><a href="#detailed_instructions">Detailed instructions</a></li>
<li><a href="#thirdparty_components">Third-party components</a></li>
<li><a href="#backups">Back-ups</a></li>
</ul>

## Quick start ##

The following brief technical instructions present a quick minimal way
to set up the brat server. If you are not sure if your setup fills the
technical requirements, please skip this section and read the detailed
instructions below.

The brat server is a
[Python](http://en.wikipedia.org/wiki/Python_%28programming_language%29)
(version 2.5+) program that runs by default as a
[CGI](http://en.wikipedia.org/wiki/Common_Gateway_Interface)
application, and the installation script assumes a UNIX-like
environment. If you are setting up brat server in a compatible
environment with an existing web server that supports CGI, the quick
start instructions for 
<a href="#quick_start_installation_using_cgi">using CGI</a> should work.
If you don't have a
web server installed and want to try brat out locally, you may want
try out the quick start instructions for the
<a href="#quick_start_installation_standalone_server">standalone server</a>. (For security
reasons, we strongly recommend serving brat via a full web server such
as Apache in production environments.)

First, download a brat package from the [brat home page](index.html).

Then, unpack the package (e.g. in the `public_html` subdirectory of
your home directory)

    tar xzf {{ site.dist.latest_stable_tgz }}

Next, enter the created brat directory

    cd {{ site.dist.latest_stable }}

The next step depends on whether you intend to run brat in a CGI
environment or as a standalone server.

### Quick start installation: using CGI ###

Run the installation script

    ./install.sh

and follow the instructions. You will be prompted for the following
information:

* brat username (e.g. "editor")
* brat password (for the given user, e.g. "annotate")
* administrator contact email (e.g. "admin@example.com")

Finally, if you are not running the installation as superuser, the
script will prompt you for the sudo password. (This is necessary to
assign write permissions to the `work` and `data` directories to the
web server.)

If this works, the installation is complete. You then only need to
make sure that CGI is permitted for the brat directory
(see the Apache 2.x section below for instructions).

### Quick start installation: standalone server ###

First, please note the following:

* The brat standalone server only is available in brat v1.3 and above.
* The standalone server is experimental and should not be used for sensitive data or systems accessible from the internet.

Run the installation script in "unprivileged" mode

    ./install.sh -u

and follow the instructions (as above). Then, start the standalone
server

    python standalone.py

You should then be able to access the brat server from the address
printed out by standalone.py. For more detail, see the
<a href="#brat_standalone_server">standalone server instructions</a>
below.

### Quick start: next steps ###

After initial installation, you may want to set up some data of your
own in your brat installation. For this, look in the 
<a href="#placing_data">Placing Data</a>
section below.

If you want to add additional users, you can edit the `config.py`
file, which contains further instructions.

If you feel that your installation requires a more fine-tuned
configuration, please see the section 
<a href="#manual_installation">Manual Installation</a> below.

If you encountered any issues with these quick start instructions,
read on for detailed instructions. You may also wish to check the
[troubleshooting](troubleshooting.html#server-trouble) page.

## Detailed Instructions ##

### Preliminaries ###

The brat server is implemented in Python, and requires version 2.5 (or
higher in the 2.x series) of python to run. If you do not currently
have python installed, we recommend installing the most recent version
of python in the 2.x series from [python.org](http://www.python.org/).

In its standard setup, brat is a served through a web server.
If you are installing brat server on a machine that is not currently 
running a web server, you should consider starting by installing one. 
brat is currently developed against
Apache 2.x, and we recommend using [Apache](http://httpd.apache.org/).

For serving brat via a web server,
These instructions primarily assume Apache, but we do have also
LigHTTPD configuration files in the repository if you prefer this
alternative, and any CGI-capable web server can be configured to run
the brat server.

Alternatively, you may wish to consider running brat using the
experimental standalone server included in version 1.3 and above.
In this case, no web server is required.

Finally, these installation instructions and parts of the brat server
assume a UNIX-like environment. These instructions should work without
changes on most linux distributions. If you are running OS X (mac),
please note a couple of OS X-specific points in the instructions below.
If you are running windows, the easiest way to run a brat server is 
in a [virtual machine](http://en.wikipedia.org/wiki/Virtual_machine)
running a UNIX-like operating system such as
[Ubuntu](http://en.wikipedia.org/wiki/Ubuntu_%28operating_system%29).

### Manual Installation ###

First, download a brat package from the [brat home page](index.html).

Then, unpack the package

    tar xzf brat-VERSION.tar.gz

(where `VERSION` is the version string, like "v1.1_Albatross").
Next, enter the created brat directory

    cd brat-VERSION

#### Setting up working directories ####

The brat server needs to read and write data to several directories.
Let's create them:

    mkdir -p data work

We now need to set the permissions of the directories so that they can
be read and written by the web server. We recommend doing this by
assigning the directories to the apache group and setting group
permissions. To do this, you will need to know the apache group. The
following script is provided for convenience for determining this

    ./apache-group.sh

(if this doesn't work, see the "Finding Your Apache 2 Group" section
of this document).

Then simply change the group of the directories (replace
`${YOUR_APACHE_GROUP}` with the output you got above) and set the
correct permissions:

    sudo chgrp -R ${YOUR_APACHE_GROUP} data work
    chmod -R g+rwx data work

If you can't succeed with the above or you are not concerned with
security (say that it is a single-user system), you can run the
command below instead. This will make the directories write-able and
read-able by every user on your system. (This is not necessary if the
command above succeeded.)

    chmod 777 data work

#### Setting up dependencies ####

brat uses [JSON](http://en.wikipedia.org/wiki/JSON) for client-server
communication. As JSON support is not included in all supported
versions of python, you may need to set up a JSON library.

First, you can determine the version of python you are running with

    python --version

if your python version is 2.5 or lower, you will need to install
an external JSON library. As of v1.2, brat supports two
JSON libraries, [UltraJSON](http://pypi.python.org/pypi/ujson/)
and [simplejson](http://pypi.python.org/pypi/ujson/). You only
need to set up one of these, and UltraJSON is recommended as it
is considerably faster. 

To install UltraJSON, run the following in the brat root directory:

    ( cd server/lib/ && unzip ujson-1.18.zip && cd ujson-1.18 &&
      python setup.py build && mv build/lib.*/ ../ujson )

If this fails, or you prefer simplejson, install simplejson as

    ( cd server/lib && tar xfz simplejson-2.1.5.tar.gz )

No other library setup is required for standard brat operation.

(if you require Japanese tokenization support, please set up
[MeCab](http://mecab.googlecode.com/svn/trunk/mecab/doc/index.html),
included in the `external/` directory.)

#### brat server configuration ####

The overall configuration of the brat server is controlled by
`config.py` in the brat root directory. This configuration file is
automatically created when running `install.sh`, but can be set up
manually as follows:

Put a configuration template in place:

   cp config_template.py config.py

Edit the configuration to suit your environment using your favorite
text editor, e.g.

    emacs config.py

Detailed instructions for setup are contained in the configuration
file itself.

#### brat standalone server ####

As of version 1.3, brat includes an experimental standalone server.
This is an alternative for running the brat server that doesn't
require a separate web server such as Apache, and can be substantially
faster, reducing server response times by 90% in some cases.

However, the standalone server is not currently security-hardened or
as comprehensively tested as the rest of brat. For these reason, we
strongly recommend serving brat via a full web server such as Apache
in production environments, projects involving sensitive data, and
on systems accessible from the internet.

On a standard installation, the brat standalone server can typically
be run simply as

    APACHE_USER=`./apache-user.sh`
    sudo -u $APACHE_USER python standalone.py

(this command will prompt for your password.)

In more detail: to run the standalone server, you need to execute the
script `standalone.py` in the brat directory. This script should have
write permissing to the working directories (normally `work/` and
`data/`). If you have set these directories up using `install.sh` or
per the instructions in the section on
<a href="#setting_up_working_directories">working directories</a>,
they should be writable by the Apache user (if one exists). The
above attempts to determine the username for Apache
(`./apache-user.sh`), and then run `standalone.py` as this user
(`sudo -u`).

If you do not have Apache installed, you may instead run the
standalone server with

    sudo -u USER python standalone.py

where `USER` is any user with write permissions to the brat work
and data directories.

### Placing Data ###

Your installation should now be ready, just place your data in the
`data` directory and make sure it has the right permissions using
`chmod` as you did above.

You can either place your data files directly in the `data` directory,
or create arbitraty directory structure under `data`. We recommend
creating a subdirectory into `data` for each (version of a) corpus you
are working on.

Brat stores its data in a [standoff](standoff.html) format, using two
files for each document: a `.txt` file containing the document text
(UTF-8 encoding), and a `.ann` file containing the annotations. To
start a new annotation project, you can simply place the `.txt` files
in the desired location and create an empty `.ann` file corresponding
to each `.txt`. After copying the `.txt` files in the `data` directory,
the `.ann` files can be created as follows:

    find data -name '*.txt' | sed -e 's|\.txt|.ann|g' | xargs touch

(Remember also to set write permissions for these files.)

You can now access your brat installation by retrieving the brat directory or
`index.xhtml` file from your web server using a
[supported web browser](supported-browsers.html).

## Third-party components ##

This part largely focuses on Ubuntu, but the instructions should be
readily applicable to other \*NIX-based systems.

### Apache 2.x ###

brat supports [FastCGI](http://www.fastcgi.com) which can speed up your
installation by roughly x10 since you won't have to invoke the Python
interpreter for every request. If you want to use FastCGI as opposed to CGI
keep an eye out for configuration comments regarding it.

<div id="notebox"><b>NOTE</b>: FastCGI support in brat is still
    somewhat experimental and there are known issues relating in
    particular to failures to reload aspects of the system on change
    to configuration files.  We recommend to only use FastCGI for
    fixed annotation configurations.
</div>

For FastCGI you need the [flup](http://trac.saddi.com/flup) Python library:

    ( cd server/lib/ && tar xfz flup-1.0.2.tar.gz )

Install Apache 2.x if you don't have it already:

    sudo apt-get install apache2

From here, the setup process is different for OS X and for other
UNIX-like systems such as linux. Please check the section relevant to
your system below.

#### Apache setup on UNIX-like systems other than OS X ####

Next, let's edit httpd.conf:

    sudo vim /etc/apache2/httpd.conf

If you are installing brat into the `public_html` subdirectory of your home
directory, add the following lines:

    <Directory /home/*/public_html>
        AllowOverride Options Indexes FileInfo Limit
        AddType application/xhtml+xml .xhtml
        AddType font/ttf .ttf
        # For CGI support
        AddHandler cgi-script .cgi
        # Comment out the line above and uncomment the line below for FastCGI
        #AddHandler fastcgi-script fcgi
    </Directory>

    # For FastCGI, Single user installs should be fine with anything over 8
    #FastCgiConfig -maxProcesses 16

If you are not installing into `public_html` in your home directory, adjust 
the above (in particular the line `<Directory /home/*/public_html>`) 
accordingly. If you installed into `public_html` in your home
directory, make sure that you have the `userdir` module enabled:

    sudo a2enmod userdir

For FastCGI you also want to install its module and then add it and the
`rewrite` module that we use to redirect the CGI requests to FastCGI:

    sudo apt-get install libapache2-mod-fastcgi
    sudo a2enmod fastcgi
    sudo a2enmod rewrite

The final FastCGI step is detailed in `.htaccess` in the brat installation
directory, which involves uncommenting and configuring the `rewrite` module.

Finally tell Apache 2.x to load your new configuration.

    sudo /etc/init.d/apache2 reload

#### Apache setup on OS X ####

Next, let's edit the apache httpd.conf:

    sudo vim /etc/apache2/users/USER.conf

where `USER` is your username.

If you are installing brat into the `Sites` directory in your home
directory, make sure the following is included:

    <Directory "/Users/USER/Sites/">
       Options Indexes MultiViews FollowSymLinks
       Order allow,deny
       Allow from all

       AllowOverride Options Indexes FileInfo Limit
       AddHandler cgi-script .cgi
       AddType application/xhtml+xml .xhtml
       AddType font/ttf .ttf
    </Directory>

where `USER` is again your username.

Finally, restart apache

    sudo apachectl restart

(For FastCGI, we're currenly trying to determine a configuration that
works on OS X and will provide instructions once we have one.)

### Finding Your Apache 2 Group ###

Ideally you should set all permissions as needed for the Apache 2 group, but
finding it can be painful.

Find out what the Apache group name is, it is usually `apache` or `www-data`;
it can be found in `apache2.conf` or `httpd.conf` under `/etc/apache2/` or
`/etc/httpd/`. Let's assume it's `www-data`. Then:

    sudo chgrp -R www-data data work
    chmod -R g+rwx data work

Actually, due to the joy of Linux segmentation you can find the group
elsewhere as well. Here is a small heuristic that works on at least two
Linux distributions:

    locate --regex '(apache2|httpd)\.conf$' | xargs cat | grep 'Group'

If what you get from this looks funky (like a variable), say with a leading $, try this:

    locate envvars | grep -E '(apache2|httpd)' | grep '/etc/' \
        | xargs cat | grep -i 'group'

If this doesn't work either dive into `/etc/group` and hope that you can find
something that at least looks like `apache` or `www-data`:

    cat /etc/group | cut -d : -f 1 | sort

## Back-ups ##

There is a script that you can use with good old `cron`.
Do as follows.

Add a line like the one below to the crontab for your Apache user:

    0 5 * * * ${PATH_TO_BRAT_INSTALLATION}/tools/backup.py

You will now have a back-up made into your work directory every morning at
five o'clock.

<div>
    <h2 style="text-align:right">
        <a href="configuration.html">
            Next: setting up annotation project configuration
        </a>
    </h2>
</div>
