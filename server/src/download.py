'''
Serves annotation related files for downloads.

Author:     Pontus Stenetorp    <pontus stenetorp se>
Version:    2011-10-03
'''

from __future__ import with_statement

from os import remove
from os.path import join as path_join, dirname, basename
from tempfile import mkstemp

from document import real_directory
from annotation import open_textfile
from common import NoPrintJSONError
from subprocess import Popen

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

def download_file(document, collection, extension):
    directory = collection
    real_dir = real_directory(directory)
    fname = '%s.%s' % (document, extension)
    fpath = path_join(real_dir, fname)

    hdrs = [('Content-Type', 'text/plain; charset=utf-8'),
            ('Content-Disposition',
                'inline; filename=%s' % fname)]
    with open_textfile(fpath, 'r') as txt_file:
        data = txt_file.read().encode('utf-8')
    raise NoPrintJSONError(hdrs, data)

def download_collection(collection, exclude_configs=False):
    directory = collection
    real_dir = real_directory(directory)
    dir_name = basename(dirname(real_dir))
    fname = '%s.%s' % (dir_name, 'tar.gz')

    tmp_file_path = None
    try:
        _, tmp_file_path = mkstemp()
        tar_cmd_split = ['tar', '--exclude=.stats_cache']
        if exclude_configs:
            tar_cmd_split.extend(['--exclude=annotation.conf',
                                  '--exclude=visual.conf',
                                  '--exclude=tools.conf',
                                  '--exclude=kb_shortcuts.conf'])
        tar_cmd_split.extend(['-c', '-z', '-f', tmp_file_path, dir_name])
        tar_p = Popen(tar_cmd_split, cwd=path_join(real_dir, '..'))
        tar_p.wait()

        hdrs = [('Content-Type', 'application/octet-stream'), #'application/x-tgz'),
                ('Content-Disposition', 'inline; filename=%s' % fname)]
        with open(tmp_file_path, 'rb') as tmp_file:
            tar_data = tmp_file.read()

        raise NoPrintJSONError(hdrs, tar_data)
    finally:
        if tmp_file_path is not None:
            remove(tmp_file_path)
