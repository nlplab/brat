'''
Serves annotation related files for downloads.

Author:     Pontus Stenetorp    <pontus stenetorp se>
Version:    2011-10-03
'''

from __future__ import with_statement

from os.path import join as path_join

from document import real_directory
from annotation import open_textfile
from common import NoPrintJSONError

def download_file(document, collection, extension):
    directory = collection
    real_dir = real_directory(directory)
    fname = '%s.%s' % (document, extension)
    fpath = path_join(real_dir, fname)

    hdrs = [('Content-Type', 'text/plain'),
            ('Content-Disposition',
                'inline; filename=%s' % fname)]
    with open_textfile(fpath) as txt_file:
        data = txt_file.read()
    raise NoPrintJSONError(hdrs, data)
