#!/usr/bin/env python

from __future__ import with_statement

'''
Provides a stylish pythonic file-lock:

>>>    with('file.lock'):
...        pass

Inspired by: http://code.activestate.com/recipes/576572/

Is *NIX specific due to being forced to use ps (suggestions on how to avoid
this are welcome).

But with added timeout and PID check to spice it all up and avoid stale
lock-files. Also includes a few unittests.

Author:     Pontus Stenetorp    <pontus stenetorp se>
Version:    2009-12-26
'''

'''
Copyright (c) 2009, 2011, Pontus Stenetorp <pontus stenetorp se>

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
'''

'''
Copyright (C) 2008 by Aaron Gallagher

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
'''

from contextlib import contextmanager
from errno import EEXIST
from os import (remove, read, fsync, open, close, write, getpid,
        O_CREAT, O_EXCL, O_RDWR, O_RDONLY)
from subprocess import Popen, PIPE
from time import time, sleep
from sys import stderr

### Constants
# Disallow ignoring a lock-file although the PID is inactive
PID_DISALLOW = 1
# Ignore a lock-file if the noted PID is not running, but warn to stderr
PID_WARN = 2
# Ignore a lock-file if the noted PID is not running
PID_ALLOW = 3
###


class FileLockTimeoutError(Exception):
    '''
    Raised if a file-lock can not be acquired before the timeout is reached.
    '''
    def __init__(self, timeout):
        self.timeout = timeout

    def __str__(self):
        return 'Timed out when trying to acquire lock, waited (%d)s' % (
                self.timeout)


def _pid_exists(pid):
    '''
    Returns True if the given PID is a currently existing process id.

    Arguments:
    pid - Process id (PID) to check if it exists on the system
    '''
    # Not elegant, but it seems that it is the only way
    ps = Popen("ps %d | awk '{{print $1}}'" % (pid, ),
            shell=True, stdout=PIPE)
    ps.wait()
    return str(pid) in ps.stdout.read().split('\n')

@contextmanager
def file_lock(path, wait=0.1, timeout=1,
        pid_policy=PID_DISALLOW, err_output=stderr):
    '''
    Use the given path for a lock-file containing the PID of the process.
    If another lock request for the same file is requested, different policies
    can be set to determine how to handle it.

    Arguments:
    path - Path where to place the lock-file or where it is in place
    
    Keyword arguments:
    wait - Time to wait between attempts to lock the file
    timeout - Duration to attempt to lock the file until a timeout exception
        is raised
    pid_policy - A PID policy as found in the module, valid are PID_DISALLOW,
        PID_WARN and PID_ALLOW
    err_output - Where to print warning messages, for testing purposes
    '''
    start_time = time()
    while True:
        if time() - start_time > timeout:
            raise FileLockTimeoutError(timeout)
        try:
            fd = open(path, O_CREAT | O_EXCL | O_RDWR)
            write(fd, str(getpid()))
            fsync(fd)
            break
        except OSError, e:
            if e.errno == EEXIST:
                if pid_policy == PID_DISALLOW:
                    pass # Standard, just do nothing
                elif pid_policy == PID_WARN or pid_policy == PID_ALLOW:
                    fd = open(path, O_RDONLY)
                    pid = int(read(fd, 255))
                    close(fd)
                    if not _pid_exists(pid):
                        # Stale lock-file
                        if pid_policy == PID_WARN:
                            print >> err_output, (
                                    "Stale lock-file '%s', deleting" % (
                                        path))
                        remove(path)
                        continue
                else:
                    assert False, 'Invalid pid_policy argument'
            else:
                raise
        sleep(wait)
    try:
        yield fd
    finally:
        close(fd)
        remove(path)

if __name__ == '__main__':
    from unittest import TestCase
    import unittest

    from multiprocessing import Process
    from os import rmdir
    from os.path import join, isfile
    from tempfile import mkdtemp

    try:
        from cStringIO import StringIO
    except ImportError:
        from StringIO import StringIO


    class TestFileLock(TestCase):
        def setUp(self):
            self._temp_dir = mkdtemp()
            self._lock_file_path = join(self._temp_dir, 'lock.file')

        def tearDown(self):
            try:
                remove(self._lock_file_path)
            except OSError:
                pass # It just didn't exist
            rmdir(self._temp_dir)

        def test_with(self):
            '''
            Tests do-with functionallity
            '''
            with file_lock(self._lock_file_path):
                sleep(1)
            sleep(0.1) # Make sure the remove is in effect
            self.assertFalse(isfile(self._lock_file_path))

        def test_exception(self):
            '''
            Tests if the lock-file does not remain if an exception occurs.
            '''
            try:
                with file_lock(self._lock_file_path):
                    raise Exception('Breaking out')
            except Exception:
                pass

            self.assertFalse(isfile(self._lock_file_path))

        def test_timeout(self):
            '''
            Test if a timeout is reached.
            '''
            # Use an impossible timeout
            try:
                with file_lock(self._lock_file_path, timeout=-1):
                    pass
                self.assertTrue(False, 'Should not reach this point')
            except FileLockTimeoutError:
                pass

        def test_lock(self):
            '''
            Test if a lock is indeed in place.
            '''
            def process_task(path):
                with file_lock(path):
                    sleep(1)
                return 0

            process = Process(target=process_task,
                    args=[self._lock_file_path])
            process.start()
            sleep(0.5) # Make sure it reaches the disk
            self.assertTrue(isfile(self._lock_file_path))
            sleep(1)

        def _fake_crash_other_process(self):
            '''
            Helper method to emulate a forced computer shutdown that leaves a
            lock-file intact.

            In theory the PID can have ended up being re-used at a later point
            but the likelihood of this can be considered to be low.
            '''
            def process_task(path):
                fd = open(path, O_CREAT | O_RDWR)
                try:
                    write(fd, str(getpid()))
                finally:
                    close(fd)
                return 0

            process = Process(target=process_task,
                    args=[self._lock_file_path])
            process.start()
            while process.is_alive():
                sleep(0.1)
            return process.pid

        def test_crash(self):
            '''
            Test that the fake crash mechanism is working.
            '''
            pid = self._fake_crash_other_process()
            self.assertTrue(isfile(self._lock_file_path))
            self.assertTrue(pid == int(
                read(open(self._lock_file_path, O_RDONLY), 255)))#XXX: Close

        ###
        def test_pid_disallow(self):
            '''
            Test if stale-lock files are respected if disallow policy is set.
            '''
            self._fake_crash_other_process()
            try:
                with file_lock(self._lock_file_path, pid_policy=PID_DISALLOW):
                    self.assertTrue(False, 'Should not reach this point')
            except FileLockTimeoutError:
                pass

        def test_pid_warn(self):
            '''
            Test if a stale lock-filk causes a warning to stderr and then is
            ignored if the warn policy is set.
            '''
            self._fake_crash_other_process()
            err_output = StringIO()
            try:
                with file_lock(self._lock_file_path, pid_policy=PID_WARN,
                        err_output=err_output):
                    pass
            except FileLockTimeoutError:
                self.assertTrue(False, 'Should not reach this point')
            err_output.seek(0)
            self.assertTrue(err_output.read(), 'No output although warn set')

        def test_pid_allow(self):
            '''
            Test if a stale lock-file is ignored and un-reported if the allow
            policy has been set.
            '''
            self._fake_crash_other_process()
            err_output = StringIO()
            try:
                with file_lock(self._lock_file_path, pid_policy=PID_ALLOW,
                        err_output=err_output):
                    pass
            except FileLockTimeoutError:
                self.assertTrue(False, 'Should not reach this point')
            err_output.seek(0)
            self.assertFalse(err_output.read(), 'Output although allow set')


    unittest.main()
