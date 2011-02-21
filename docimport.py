#!/usr/bin/env python

'''
Simple interface to for importing files into the data directory.

Author:     Pontus Stenetorp    <pontus is s u-tokyo ac jp>
Version:    2011-02-21
'''

#XXX: Currently you need to create the DEFAULT_IMPORT_DIR manually!

from config import DATA_DIR
from annotation import JOINED_ANN_FILE_SUFF, TEXT_FILE_SUFFIX
from os.path import join as join_path
from os.path import isdir, isfile
from os import access, W_OK

### Constants
DEFAULT_IMPORT_DIR = 'import'
###


class InvalidDirError(Exception):
    def __init__(self, path):
        self.path = path


class FileExistsError(Exception):
    def __init__(self, path):
        self.path = path


class NoWritePermissionError(Exception):
    def __init__(self, path):
        self.path = path


#TODO: Chop this function up
def save_import(text, filename, relative_dir=None, data_dir=None):
    '''
    TODO: DOC:
    '''

    if data_dir is None:
        data_dir = DATA_DIR
    
    if relative_dir is None:
        dir_path = join_path(data_dir, DEFAULT_IMPORT_DIR)
    else:
        #XXX: These "security" measures can surely be fooled, too restrictive
        if (relative_dir[0] == '/'
                or relative_dir.count('../') or relative_dir == '..'):
            raise InvalidDirError(relative_dir)
        dir_path = join_path(data_dir, relative_dir)

    # Is the directory a directory and are we allowed to write?
    if not isdir(dir_path):
        raise InvalidDirError(dir_path)
    if not access(dir_path, W_OK):
        raise NoWritePermissionError(dir_path)

    base_path = join_path(dir_path, filename)
    txt_path = base_path + '.' + TEXT_FILE_SUFFIX
    ann_path = base_path + '.' + JOINED_ANN_FILE_SUFF

    # Before we proceed, verify that we are not overwriting
    for path in (txt_path, ann_path):
        if isfile(path):
            raise FileExistsError(path)

    with open(txt_path, 'w') as txt_file:
        txt_file.write(text)

    # Touch the ann file so that we can edit the file later
    with open(ann_path, 'w') as _:
        pass

if __name__ == '__main__':
    from unittest import TestCase
    from tempfile import mkdtemp
    from shutil import rmtree
    from os import mkdir


    class SaveImportTest(TestCase):
        test_text = 'This is not a drill, this is a drill *BRRR!*'
        test_dir = 'test'
        test_filename = 'test'

        def setUp(self):
            self.tmpdir = mkdtemp()
            mkdir(join_path(self.tmpdir, SaveImportTest.test_dir))
            mkdir(join_path(self.tmpdir, DEFAULT_IMPORT_DIR))

        def tearDown(self):
            #rmtree(self.tmpdir)
            print self.tmpdir

        def test_import(self):
            save_import(SaveImportTest.test_text, SaveImportTest.test_filename,
                    relative_dir=SaveImportTest.test_dir,
                    data_dir=self.tmpdir)
        
        def test_default_import_dir(self):
            save_import(SaveImportTest.test_text, SaveImportTest.test_filename,
                    data_dir=self.tmpdir)
   

    import unittest
    unittest.main()
