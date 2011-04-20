#!/usr/bin/env python

from __future__ import with_statement

'''
Back-up mechanisms for the data directory.

Author:     Pontus Stenetorp    <pontus is s u-tokyo ac jp>
Version:    2011-02-22
'''

#XXX: We can potentially miss a change within the same second as the back-up,
#       we need to share a mutex with the rest of the system somehow
#XXX: Does not check the return values of the external calls
#XXX: File/directory permissions must be checked
#XXX: The check for the latest data ASSUMES that the data dir has not been
#       changed, if it has been changed it will not do a back-up although
#       there is no existing back-up

from os.path import getmtime, isfile, dirname, abspath, basename
from os.path import join as join_path
from shlex import split as split_shlex
from datetime import datetime, timedelta
from os import listdir, walk
from subprocess import Popen, PIPE

from filelock import file_lock, PID_WARN

from config import BACKUP_DIR, DATA_DIR

### Constants
#TODO: Move to a config
MIN_INTERVAL = timedelta(days=1)
CHECKSUM_FILENAME = 'CHECKSUM'
TAR_GZ_SUFFIX = 'tar.gz'
###

def _datetime_mtime(path):
    return datetime.fromtimestamp(getmtime(path))

def _safe_dirname(path):
    # This handles the case of a trailing slash for the dir path
    return basename(path) or dirname(dirname(path))

# NOTE: Finds the younges file in a directory structure, currently not in use
#       due to performance problems
'''
def _youngest_file(dir):
    youngest = dir
    y_mtime = _datetime_mtime(dir)
    for root, _, files in walk(dir):
        for file_path in (join_path(root, f) for f in files):
            f_mtime = _datetime_mtime(file_path)
            if f_mtime > y_mtime:
                youngest = file_path
                y_mtime = f_mtime
    return youngest, y_mtime
'''

def _youngest_backup(dir):
    backups = [(_datetime_mtime(f), f)
            for f in (join_path(dir, p) for p in listdir(dir))
            if isfile(f) and f.endswith('.' + TAR_GZ_SUFFIX)]
    if not backups:
        # We found no backups
        return None, None
    backups.sort()
    # Flip the order since the path should be first and mtime second
    return backups[0][::-1]

def backup(min_interval=MIN_INTERVAL, backup_dir=BACKUP_DIR, data_dir=DATA_DIR):
    if backup_dir is None:
        return

    #XXX: The timeout is arbitary but dependant on the back-up, should we start
    #       with a sane default and then refer to how long the last back-up
    #       took?  
    backup_lock = join_path(DATA_DIR, '.backup.lock')
    with file_lock(backup_lock, pid_policy=PID_WARN, timeout=60):
        _backup(min_interval, backup_dir, data_dir)

def _backup(min_interval=MIN_INTERVAL, backup_dir=BACKUP_DIR, data_dir=DATA_DIR):
    b_file, b_mtime = _youngest_backup(backup_dir)
    y_mtime = _datetime_mtime(DATA_DIR)
    #_, y_mtime = _youngest_file(data_dir)
    # If we have a back-up arch and no file has changed since the back-up or
    #       the delay has not expired, return
    if b_file is not None and (y_mtime <= b_mtime
            or (y_mtime - b_mtime) < min_interval):
        return

    # Here we do use UTC
    backup_filename = (_safe_dirname(data_dir) + '-'
            + datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
            + '.' + TAR_GZ_SUFFIX)
    backup_path = abspath(join_path(backup_dir, backup_filename))
    data_dir_parent = join_path(data_dir, '../')

    #TODO: Check the exit signals!
    cmd = 'tar -c -z -f %s -C %s %s' % (backup_path,
        data_dir_parent, _safe_dirname(data_dir))
    tar_p = Popen(split_shlex(cmd))
    tar_p.wait()

    checksum_base = join_path(backup_dir, CHECKSUM_FILENAME)
    with open(checksum_base + '.' + 'MD5', 'a') as md5_file:
        # *NIX could have used m5sum instead
        md5_cmd = 'md5sum %s' % (backup_filename)
        md5_p = Popen(split_shlex(md5_cmd), stdout=md5_file, cwd=backup_dir)
        md5_p.wait()

    with open(checksum_base + '.' + 'SHA256', 'a') as sha256_file:
        sha256_cmd = 'shasum -a 256 %s' % (backup_filename)
        sha256_p = Popen(split_shlex(sha256_cmd), stdout=sha256_file, cwd=backup_dir)
        sha256_p.wait()

if __name__ == '__main__':
    from unittest import TestCase
    from tempfile import mkdtemp
    from shutil import rmtree
    from time import sleep
    
    def _backups(dir):
        return len([f for f in listdir(dir)
            if f.endswith('.' + TAR_GZ_SUFFIX)])

    #TODO: Use a wrapped back-up, as it is now it is easy to mess up the paths
    class BackupTest(TestCase):
        dummy_filename = 'dummy'

        def setUp(self):
            self.tmp_dir = mkdtemp()
            self.data_dir = mkdtemp()
            self.dummy_path = join_path(self.data_dir,
                    BackupTest.dummy_filename)
            with open(self.dummy_path, 'w') as _:
                pass

        def tearDown(self):
            rmtree(self.tmp_dir)
            rmtree(self.data_dir)

        def test_empty(self):
            backup(backup_dir=self.tmp_dir, data_dir=self.data_dir)
            self.assertTrue(_backups(self.tmp_dir),
                    'no back-up was created upon empty backup dir')

        def test_delay(self):
            backup(backup_dir=self.tmp_dir, data_dir=self.data_dir)
            backup(min_interval=timedelta(days=365),
                    backup_dir=self.tmp_dir, data_dir=self.data_dir)
            self.assertTrue(_backups(self.tmp_dir) == 1,
                    'additional backup created although delay had not expired')

        def test_no_change(self):
            backup(backup_dir=self.tmp_dir, data_dir=self.data_dir)
            sleep(3)
            backup(min_interval=timedelta(seconds=1),
                    backup_dir=self.tmp_dir, data_dir=self.data_dir)
            self.assertTrue(_backups(self.tmp_dir) == 1,
                    'additional back-up created although no file changed')

        def test_expired_delay(self):
            backup(backup_dir=self.tmp_dir, data_dir=self.data_dir)
            sleep(3)
            with open(self.dummy_path, 'w') as dummy_file:
                dummy_file.write('This is a change for a change')
            sleep(3)
            backup(min_interval=timedelta(seconds=1),
                    backup_dir=self.tmp_dir, data_dir=self.data_dir)
            self.assertTrue(_backups(self.tmp_dir) == 2,
                    'no additional back-up was created after delay expired')

    import unittest
    unittest.main()
