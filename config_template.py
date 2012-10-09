# This configuration file specifies the global setup of the brat
# server. It is recommended that you use the installation script
# instead of editing this file directly. To do this, run the following
# command in the brat directory:
#
#     ./install.sh
#
# if you wish to configure the server manually, you will first need to
# make sure that this file appears as config.py in the brat server
# root directory. If this file is currently named config_template.py,
# you can do this as follows:
#
#     cp config_template.py config.py
#
# you will then need to edit config.py, minimally replacing all 
# instances of the string CHANGE_ME with their appropriate values.
# Please note that these values MUST appear in quotes, e.g. as in
#
# ADMIN_CONTACT_EMAIL = 'admin@example.com'



# Contact email for users to use if the software encounters errors
ADMIN_CONTACT_EMAIL = CHANGE_ME

# Directories required by the brat server:
#
#     BASE_DIR: directory in which the server is installed
#     DATA_DIR: directory containing texts and annotations
#     WORK_DIR: directory that the server uses for temporary files
#
BASE_DIR = CHANGE_ME
DATA_DIR = CHANGE_ME
WORK_DIR = CHANGE_ME

# If you have installed brat as suggested in the installation
# instructions, you can set up BASE_DIR, DATA_DIR and WORK_DIR by
# removing the three lines above and deleting the initial '#'
# character from the following four lines:

#from os.path import dirname, join
#BASE_DIR = dirname(__file__)
#DATA_DIR = join(BASE_DIR, 'data')
#WORK_DIR = join(BASE_DIR, 'work')

# To allow editing, include at least one USERNAME:PASSWORD pair below.
# The format is the following:
#
#     'USERNAME': 'PASSWORD',
#
# For example, user `editor` and password `annotate`:
#
#     'editor': 'annotate',

USER_PASSWORD = {
#     (add USERNAME:PASSWORD pairs below this line.)
}





########## ADVANCED CONFIGURATION OPTIONS ##########

# The following options control advanced aspects of the brat server
# setup.  It is not necessary to edit these in a basic brat server
# installation.


### MAX_SEARCH_RESULT_NUMBER
# It may be a good idea to limit the max number of results to a search
# as very high numbers can be demanding of both server and clients.
# (unlimited if not defined or <= 0)

MAX_SEARCH_RESULT_NUMBER = 1000


### DEBUG
# Set to True to enable additional debug output

DEBUG = False


### LOG_LEVEL
# If you are a developer you may want to turn on extensive server
# logging by enabling LOG_LEVEL = LL_DEBUG

LL_DEBUG, LL_INFO, LL_WARNING, LL_ERROR, LL_CRITICAL = range(5)
LOG_LEVEL = LL_WARNING
#LOG_LEVEL = LL_DEBUG

### BACKUP_DIR
# Define to enable backups

# from os.path import join
#BACKUP_DIR = join(WORK_DIR, 'backup')

try:
    assert DATA_DIR != BACKUP_DIR, 'DATA_DIR cannot equal BACKUP_DIR'
except NameError:
    pass # BACKUP_DIR most likely not defined


### SVG_CONVERSION_COMMANDS
# If export to formats other than SVG is needed, the server must have
# a software capable of conversion like inkscape set up, and the
# following must be defined.
# (SETUP NOTE: at least Inkscape 0.46 requires the directory
# ".gnome2/" in the apache home directory and will crash if it doesn't
# exist.)

#SVG_CONVERSION_COMMANDS = [
#    ('png', 'inkscape --export-area-drawing --without-gui --file=%s --export-png=%s'),
#    ('pdf', 'inkscape --export-area-drawing --without-gui --file=%s --export-pdf=%s'),
#    ('eps', 'inkscape --export-area-drawing --without-gui --file=%s --export-eps=%s'),
#]
