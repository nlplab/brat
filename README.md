# About brat #

*brat* (brat rapid annotation tool) is based on the
[stav](https://github.com/TsujiiLaboratory/stav/) visualiser which was
originally constructed for
[BioNLP'11 Shared Task](https://sites.google.com/site/bionlpst/) data.

Currently brat is under heavy development but is used to annotated data by the
[Genia](http://www-tsujii.is.s.u-tokyo.ac.jp/GENIA/) group at the University
of Tokyo. brat aims to provide an intuitive and fast way to create text-bound
and relational annotations.

It also aims to overcome short-comings with previous annotation tools such as:

* De-centralisation of configurations and data, causing syncronisation issues
* Split between annotations and related text
* Complexity of set-up for annotators
* Etc.

brat does this by:

* Data and configurations on a central web server ("put all your eggs in one
basket and guard the damn basket")
* Present text as it would appear to a reader and maintain annotations close
to the text
* Zero set-up for annotators, leave configurations and server/data maintainence
to other staff

# License #

Please see LICENSE.

# Installation #

This section describes how to install brat and third-party dependencies.

## WARNING ##

Since brat (and this document) is very much under development the information
on this document may not be up to date. If not, bash the developers ASAP.

## brat ##

Extract brat somewhere convenient:

    tar xzf TsujiiLaboratory-brat-${VERSION}-${HASH}.tar.gz

Enter the brat directory:

    cd brat

When running brat it needs to write data to several directories, let's create
them.

    mkdir data work

We now need to set the permissions of these directories so that they can be
read and written by Apache. The command-line below is likely to give you the
Apache 2 group if you have Apache currently running. If not, see the "Finding
Your Apache 2 Group" section of this document:

    groups `ps aux | grep apache | grep -v 'grep' \
            | cut -d ' ' -f 1 | grep -v 'root' | head -n 1` \
        | cut -d : -f 2 | sed 's|\ ||g'

Then simply change the group of the directories (change `${YOUR_APACHE_GROUP}`
into the output you got above) and set the correct permissions:

    sudo chgrp -R ${YOUR_APACHE_GROUP} data sessions svg
    chmod -R g+rwx data work

If you can't succeed with the above or you are not concerned with security (say
that it is a single-user system), you can run the command below instead or
refer to your operating system manual and look-up Apache 2 for their
instructions on how to get the Apache group. This will make the directories
write-able and read-able by every user on your system:

    chmod 777 data work

Extract all the library dependencies.

    ( cd server/lib && tar xfz simplejson-2.1.5.tar.gz )

And extract and compile
[GeniaSS](http://www-tsujii.is.s.u-tokyo.ac.jp/~y-matsu/geniass/):

    ( cd external && tar xfz geniass-1.00.tar.gz && cd geniass && make )

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

## Third-party Stuff ##

This part largely focuses on Ubuntu, but use your \*NIX-foo to turn it into what
you need if you don't have the misfortune to have the
"Brown Lunix Distribution".

### Apache 2 ###

Install apache2, maybe you have a package manager.

    sudo apt-get install apache2

Let's edit the httpd.conf.

    sudo vim /etc/apache2/httpd.conf

If you are installing brat into your home directory, add the following four
lines.

    <Directory /home/*/public_html>
        AllowOverride Options Indexes
        AddHandler cgi-script .cgi
        AddType application/xhtml+xml .xhtml
        AddType font/ttf .ttf
    </Directory>

And make sure that you have the userdir module enabled.

    sudo a2enmod userdir

Finally tell apache2 to load your new config.

    sudo /etc/init.d/apache2 reload

### Finding Four Apache 2 Group ###

Ideally you should set all permissions as needed for the Apache 2 group, but
finding it can be painful.

Find out what the Apache group name is, it is usually `apache` or `www-data`;
it can be found in `apache2.conf` or `httpd.conf` under `/etc/apache2/` or
`/etc/httpd/`. Let's assume it's www-data. Then:

    sudo chgrp -R www-data data sessions svg
    chmod -R g+rwx data sessions svg

Actually, due to the joy of Linux segmentation you can find the group
elsewhere as well. Here is a small heuristic that works on at least two
distributions:

    locate --regex '(apache2|httpd)\.conf$' | xargs cat | grep 'Group'

If what you get from this looks funky, say with a leading $, try this:

    locate envvars | grep -E '(apache2|httpd)' | grep '/etc/' \
        | xargs cat | grep -i 'group'

If this doesn't work either dive into `/etc/group` and hope that you can find
something that at least looks like `apache` or `www-data`:

    cat /etc/group | cut -d : -f 1 | sort

## On a Mac ##

On a Mac, Apache configuration is quite different, and Aptitude is not
available.

### Setting up Apache ###

Clone this repository into `~/Sites`. Edit
`/private/etc/apache2/users/$USER.conf`. Then invoke `sudo apachectl reload`.
The default user and group name for Apache is `_www` (as found in
`/private/etc/apache2/httpd.conf`), for use in `chgrp`.

# Back-ups #
brat has a very flaky back-up system (actually my fault for my early morning
hack), there is an alternate script that you can use with good old `cron`.
Do as follows.

Add a line like the one below to the crontab for your Apache user:

    0 5 * * * ${PATH_TO_BRAT_INSTALLATION}/tools/backup.py

You will now have a back-up made into your work directory every morning at
five o'clock.
