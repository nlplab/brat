# brat rapid annotation tool (brat) #

## About ##

*brat* (brat rapid annotation tool) is based on the [stav][stav] visualiser
which was originally made in order to visualise
[BioNLP'11 Shared Task][bionlp_2011_st] data. Currently brat is under heavy
development but is used by [Genia][genia] and several external groups for
ongoing annotation projects. brat aims to provide an intuitive and fast way to
create text-bound and relational annotations.

[stav]:             https://github.com/TsujiiLaboratory/stav/
[bionlp_2011_st]:   https://sites.google.com/site/bionlpst/
[genia]:            http://www-tsujii.is.s.u-tokyo.ac.jp/GENIA/

brat aims to overcome short-comings of previous annotation tools such as:

* De-centralisation of configurations and data, causing synchronisation issues
* Annotations and related text not being visually adjacent
* Complexity of set-up for annotators
* Etc.

brat does this by:

* Data and configurations on a central web server (as Mark Twain said:
"Put all your eggs in one basket, and then guard that basket!")
* Present text as it would appear to a reader and maintain annotations close
to the text
* Zero set-up for annotators, leave configurations and server/data maintainence
to other staff

## Citing ##

If you do make use of brat or components from brat, please do cite us in your
related publications.

We are currently preparing a publication for brat and would appreciate if the
software is referred to as "an annotation tool based on the stav visualiser"
to avoid any potential confusion regarding prior publications.

Thus in the meantime use the following publication:

    @InProceedings{stenetorp2011supporting,
      author    = {Stenetorp, Pontus and Topi\'{c}, Goran and Pyysalo, Sampo
          and Ohta, Tomoko and Kim, Jin-Dong and Tsujii, Jun'ichi},
      title     = {BioNLP Shared Task 2011: Supporting Resources},
      booktitle = {Proceedings of BioNLP Shared Task 2011 Workshop},
      month     = {June},
      year      = {2011},
      address   = {Portland, Oregon, USA},
      publisher = {Association for Computational Linguistics},
      pages     = {112--120},
      url       = {http://www.aclweb.org/anthology/W11-1816}
    }

If you have enough space we would be very happy if you also link to the stav
repository which will later contain a link to the brat repository after brat
is published:

    ...the stav text annotation visualiser\footnote{
        \url{https://github.com/TsujiiLaboratory/stav}
    }

## License ##

Please see LICENSE.

## Installation ##

This section describes how to install brat and its third-party dependencies.
Do note that brat is a served through a web server and we currently develop
against Apache 2.x, these instructions will assume that you use the same but
we do have LigHTTPD configuration files in the repository if you feel like
trying it out.

### WARNING ###

Since brat (and this document) is very much under development the information
on this document may not be up to date. If it isn't, bash the developers ASAP.
You are also very welcome to file issues for bugs that you may find or
features that you would like to see in brat, do so at
[our GitHub page][issues] or by mailing the authors. We appreciate if you
supply the version you are working on and as much details on your system as
possible (we have received tar-balls of whole installations at some points
since the installation can be self-contained in a single directory).

[issues]: https://github.com/TsujiiLaboratory/brat/issues

### brat ###

Extract brat somewhere convenient where your webserver can reach it:

    tar xzf TsujiiLaboratory-brat-${VERSION}-${HASH}.tar.gz

Enter the brat directory:

    cd brat

When running brat it needs to read and write data to several directories,
let's create them.

    mkdir data work

We now need to set the permissions of the directories so that they can be
read and written by the webserver. The command-line below is likely to give
you the Apache 2 group if you have Apache currently running. If not, see the
"Finding Your Apache 2 Group" section of this document:

    groups `ps aux | grep apache | grep -v 'grep' \
            | cut -d ' ' -f 1 | grep -v 'root' | head -n 1` \
        | cut -d : -f 2 | sed 's|\ ||g'

Then simply change the group of the directories (change `${YOUR_APACHE_GROUP}`
into the output you got above) and set the correct permissions:

    sudo chgrp -R ${YOUR_APACHE_GROUP} data work
    chmod -R g+rwx data work

If you can't succeed with the above or you are not concerned with security (say
that it is a single-user system), you can run the command below instead or
refer to your operating system manual and look-up Apache 2 for their
instructions on how to get the Apache group. This will make the directories
write-able and read-able by every user on your system:

    chmod 777 data work

Extract all the library dependencies.

    ( cd server/lib && tar xfz simplejson-2.1.5.tar.gz )

Put a configuration in place.

    cp config_template.py config.py

Edit the configuration to suit your environment.

    vim config.py

Your installation should now be ready, just place your data in the `data`
directory and make sure it has the right permissions using `chmod` as you did
above. If your data consists of no prior annotations and only `.txt` files,
create the annotation files (`.ann`) as below.

    ( find data -name '*.txt' | sed -e 's|\.txt||g' \
        | xargs -I {} touch '{}.ann' )

### Third-party Stuff ###

This part largely focuses on Ubuntu, but use your \*NIX-fu to turn it into what
you need if you don't have the misfortune to have the
"Brown Lunix Distribution".

#### Apache 2.x ####

brat supports [FastCGI][fastcgi] which can speed up your installation by
roughly x10 since you won't have to invoke the Python interpreter for every
request. If you want to use FastCGI as opposed to CGI keep an eye out for
configuration comments regarding it. For FastCGI you need the [flup][flup]
Python library:

    ( cd server/lib/ && tar xfz flup-1.0.2.tar.gz )

[fastcgi]:  http://www.fastcgi.com/
[flup]:     http://trac.saddi.com/flup

Install Apache 2.x if you don't have it already:

    sudo apt-get install apache2

Let's edit the httpd.conf.

    sudo vim /etc/apache2/httpd.conf

If you are installing brat into your home directory, add the following lines.

    <Directory /home/*/public_html>
        AllowOverride Options Indexes
        AddType application/xhtml+xml .xhtml
        AddType font/ttf .ttf
        # For CGI support
        AddHandler cgi-script .cgi
        # Comment out the line above and uncomment the lines below for FastCGI
        #<IfModule mod_fastcgi.c>
        #    # Single user installations should be fine with anything over 8
        #    FastCgiConfig -maxProcesses 16
        #    AddHandler fastcgi-script fcgi
        #</IfModule>
    </Directory>

If you are not installing into your home directory adjust the above lines
accordingly. If you installed into your home directory make sure that you have
the `userdir` module enabled.

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

#### Finding Four Apache 2 Group ####

Ideally you should set all permissions as needed for the Apache 2 group, but
finding it can be painful.

Find out what the Apache group name is, it is usually `apache` or `www-data`;
it can be found in `apache2.conf` or `httpd.conf` under `/etc/apache2/` or
`/etc/httpd/`. Let's assume it's www-data. Then:

    sudo chgrp -R www-data data work
    chmod -R g+rwx data work

Actually, due to the joy of Linux segmentation you can find the group
elsewhere as well. Here is a small heuristic that works on at least two
Linux distributions:

    locate --regex '(apache2|httpd)\.conf$' | xargs cat | grep 'Group'

If what you get from this looks funky, say with a leading $, try this:

    locate envvars | grep -E '(apache2|httpd)' | grep '/etc/' \
        | xargs cat | grep -i 'group'

If this doesn't work either dive into `/etc/group` and hope that you can find
something that at least looks like `apache` or `www-data`:

    cat /etc/group | cut -d : -f 1 | sort

### On a Mac ###

On a Mac, Apache configuration is quite different, and Aptitude is not
available.

#### Setting up Apache ####

Clone this repository into `~/Sites`. Edit
`/private/etc/apache2/users/$USER.conf`. Then invoke `sudo apachectl reload`.
The default user and group name for Apache is `_www` (as found in
`/private/etc/apache2/httpd.conf`), for use in `chgrp`.

## Back-ups ##

brat had a very flaky back-up system (actually my fault for my early morning
hack), there is an alternate script that you can use with good old `cron`.
Do as follows.

Add a line like the one below to the crontab for your Apache user:

    0 5 * * * ${PATH_TO_BRAT_INSTALLATION}/tools/backup.py

You will now have a back-up made into your work directory every morning at
five o'clock.

## Contact ##

For help and feedback please contact the authors below, preferably with all on
them on CC since their responsibilities and availability may vary:

* Goran Topić       &lt;goran is s u-tokyo ac jp&gt;
* Sampo Pyysalo     &lt;smp is s u-tokyo ac jp&gt;
* Pontus Stenetorp  &lt;pontus is s u-tokyo ac jp&gt;
