#!/usr/bin/env python

'''
Simple wrapper for GeniaSS and its post-processor by Sampo Pyysalo.

http://www-tsujii.is.s.u-tokyo.ac.jp/~y-matsu/geniass/

Author:     Pontus Stenetorp <pontus stenetorp se>
Version:    2011-02-03
'''

from os.path import isfile, dirname, join, abspath
from subprocess import Popen, PIPE
from tempfile import NamedTemporaryFile
from shlex import split as shlex_split

#XXX: We assume that we are allowed to pollute the file directory with caches

### Contants
CACHE_SUFFIX = 'ss'
# TODO: This goes in a config file?
TOOLS_DIR = abspath(join(dirname(__file__), 'tools'))
GENIASS_DIR_PATH = join(TOOLS_DIR, 'geniass')
GENIASS_PATH = join(GENIASS_DIR_PATH, 'run_geniass.sh')
GENIASS_POST_PATH = join(TOOLS_DIR, 'geniass-postproc.pl')
###

#TODO: Enable the cache by default
#TODO: If we are called with use_cache false we should not leave a .ss around
def sentence_split_file(txt_file_path, use_cache=False):
    ss_file_path = txt_file_path + '.' + CACHE_SUFFIX 
    if use_cache:
        if isfile(ss_file_path):
            with open(ss_file_path, 'r') as ss_file:
                return ss_file.read()
   
    # Get a temporary file to which GeniaSS can write output
    with NamedTemporaryFile('r') as temp_file, open('/dev/null', 'w') as null:
        # Use GeniaSS to generate an intermediate file
        geniass_p = Popen(shlex_split('{} {} {}'.format(GENIASS_PATH,
            txt_file_path, temp_file.name)), stderr=null)
        geniass_p.wait()
        # Then post-process it to correct errors
        geniass_post_p = Popen(shlex_split('{} {}'.format(
            GENIASS_POST_PATH, temp_file.name)), stdout=PIPE)
        geniass_post_p.wait()
        ss_output = geniass_post_p.stdout.read()

        # Save the output if we are to use a cache
        if use_cache:
            with open(ss_file_path, 'w') as ss_file:
                ss_file.write(ss_output)

        return ss_output

if __name__ == '__main__':
    from unittest import TestCase
    from os import remove

    import unittest

    #TODO: More tests if necessary, this is a simple one.
    class TestSequenceFunctions(TestCase):
        single_split_txt = 'These here. Are two sentences.'
        single_split_txt_ss = 'These here.\nAre two sentences.'

        def setUp(self):
            with NamedTemporaryFile('w', delete=False) as tmp_file:
                tmp_file.write(TestSequenceFunctions.single_split_txt) 
                self.tmp_file_path = tmp_file.name

        def tearDown(self):
            remove(self.tmp_file_path)

        def test_single_split(self):
            # Simple test of splitting a single sentence
            self.assertEqual(TestSequenceFunctions.single_split_txt_ss,
                sentence_split_file(self.tmp_file_path))

        def test_cache(self):
            # Two cached calls return the same data
            self.assertEqual(
                    sentence_split_file(self.tmp_file_path, use_cache=True),
                    sentence_split_file(self.tmp_file_path, use_cache=True))

        def test_no_cache(self):
            # Make sure that no cache file is created
            sentence_split_file(self.tmp_file_path, use_cache=False)
            self.assertFalse(isfile(self.tmp_file_path + '.' + CACHE_SUFFIX))

    unittest.main()
