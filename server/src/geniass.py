#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

from __future__ import with_statement

'''
Simple wrapper for GeniaSS and its post-processor by Sampo Pyysalo.

http://www-tsujii.is.s.u-tokyo.ac.jp/~y-matsu/geniass/

Author:     Pontus Stenetorp <pontus stenetorp se>
Version:    2011-02-03
'''

from os.path import isfile, dirname, join, abspath
from os import access, R_OK, W_OK
from subprocess import Popen, PIPE
from tempfile import NamedTemporaryFile
from shlex import split as shlex_split

#XXX: We assume that we are allowed to pollute the file directory with caches

### Contants
CACHE_SUFFIX = 'ss'
# TODO: This goes in a config file?
EXTERN_DIR = abspath(join(dirname(__file__), '..', '..', 'external'))
GENIASS_DIR_PATH = join(EXTERN_DIR, 'geniass')
GENIASS_PATH = join(GENIASS_DIR_PATH, 'run_geniass.sh')
GENIASS_POST_PATH = join(EXTERN_DIR, 'geniass-postproc.pl')
###

#XXX: Our current way of ignoring on non-R_OK and non-W_OK is really silent
#       errors, we fail to complete the requested action.
#TODO: Enable the cache by default?
#TODO: Point out that the cache needs to be purged when the text is changed
#TODO: If we are called with use_cache false we should not leave a .ss around
def sentence_split_file(txt_file_path, use_cache=False):
    ss_file_path = txt_file_path + '.' + CACHE_SUFFIX 
    if use_cache:
        # Read the cache if we are allowed to
        if isfile(ss_file_path) and access(ss_file_path, R_OK):
            with open(ss_file_path, 'r') as ss_file:
                return ss_file.read()
   
    # Get a temporary file to which GeniaSS can write output
    with NamedTemporaryFile('r') as temp_file:
        with open('/dev/null', 'w') as null:
            # Use GeniaSS to generate an intermediate file
            geniass_p = Popen(shlex_split('%s %s %s' % (GENIASS_PATH,
                txt_file_path, temp_file.name)), stderr=null)
            geniass_p.wait()
            # Then post-process it to correct errors
            geniass_post_p = Popen(shlex_split('%s %s' % (
                GENIASS_POST_PATH, temp_file.name)), stdout=PIPE)
            geniass_post_p.wait()
            ss_output = geniass_post_p.stdout.read()

            # Save the output if we are to use a cache and may write
            if use_cache and access(dirname(ss_file_path), W_OK):
                with open(ss_file_path, 'w') as ss_file:
                    ss_file.write(ss_output)

            return ss_output

if __name__ == '__main__':
    from unittest import TestCase
    from os import remove, chmod, stat
    from random import randint
    from tempfile import mkdtemp
    from shutil import rmtree

    import unittest

    #TODO: More tests if necessary, this is a simple one.
    class TestSequenceFunctions(TestCase):
        single_split_txt = 'These here. Are two sentences.'
        single_split_txt_ss = 'These here.\nAre two sentences.'

        def setUp(self):
            self.tmp_dir = mkdtemp()
            with NamedTemporaryFile('w', delete=False,
                    dir=self.tmp_dir) as tmp_file:
                tmp_file.write(TestSequenceFunctions.single_split_txt) 
                self.tmp_file_path = tmp_file.name

        def tearDown(self):
            remove(self.tmp_file_path)
            # Also remove a potential sentence split file
            try:
                remove(self.tmp_file_path + CACHE_SUFFIX)
            except OSError:
                pass
            
            # Lastly, remove the directory, forcefully
            rmtree(self.tmp_dir)

        def test_single_split(self):
            # Simple test of splitting a single sentence
            self.assertEqual(TestSequenceFunctions.single_split_txt_ss,
                sentence_split_file(self.tmp_file_path))

        def test_cache(self):
            # Two cached calls return the same data
            first_call = sentence_split_file(self.tmp_file_path, use_cache=True)
            # Modify the data
            with open(self.tmp_file_path, 'w') as tmp_file:
                tmp_file.write(str(randint(0, 4711)))
            self.assertEqual(first_call,
                    sentence_split_file(self.tmp_file_path, use_cache=True))

        def test_no_cache(self):
            # Make sure that no cache file is created
            sentence_split_file(self.tmp_file_path, use_cache=False)
            self.assertFalse(isfile(self.tmp_file_path + '.' + CACHE_SUFFIX))

        def test_no_read(self):
            # Create and read a fake cache file
            fake_cache_path = self.tmp_file_path + CACHE_SUFFIX
            with open(fake_cache_path, 'w') as fake_cache:
                fake_cache.write(str(randint(0, 4711)))
            with open(fake_cache_path, 'r') as fake_cache:
                fake_cache_data = fake_cache.read()
            # Make sure that we don't have read permissions to the cache
            old_perm = stat(fake_cache_path)[0]
            chmod(fake_cache_path, 0x0)
            self.assertEqual(
                    sentence_split_file(self.tmp_file_path, use_cache=True),
                    TestSequenceFunctions.single_split_txt_ss)
            # Restore the permissions
            chmod(fake_cache_path, old_perm)
            # Assert that the file is unchanged
            with open(fake_cache_path, 'r') as fake_cache:
                self.assertEqual(fake_cache_data, fake_cache.read())

        def test_no_write(self):
            chmod(self.tmp_file_path, 0x0)
            pass

    unittest.main()
