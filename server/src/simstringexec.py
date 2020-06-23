from subprocess import Popen, PIPE, run
from simstringbase import SimstringBase, test
from os.path import isfile
import select


# make sure the simstring executable can be run
try:
    from config import SIMSTRING_EXECUTABLE
except ImportError:
    from shutil import which
    SIMSTRING_EXECUTABLE = which('simstring')
simstring_found = SIMSTRING_EXECUTABLE and isfile(SIMSTRING_EXECUTABLE)


class SimstringExecException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return 'Simstring error: %s' % self.message


class SimstringExec(SimstringBase):
    def __init__(self, dbfn,
            ngram_length=SimstringBase.DEFAULT_NGRAM_LENGTH,
            include_marks=SimstringBase.DEFAULT_INCLUDE_MARKS,
            threshold=SimstringBase.DEFAULT_THRESHOLD,
            similarity_measure=SimstringBase.DEFAULT_SIMILARITY_MEASURE,
            unicode=SimstringBase.DEFAULT_UNICODE,
            build=False):

        super().__init__(dbfn,
                ngram_length=ngram_length,
                include_marks=include_marks,
                threshold=threshold,
                similarity_measure=similarity_measure,
                unicode=unicode,
                build=build)

        self.proc = None
        from message import Messager
        if not simstring_found:
            Messager.error("Error: simstring not found (Hint: set SIMSTRING_EXECUTABLE in config.py")
            return

        cmd = [SIMSTRING_EXECUTABLE,
                "-d", self.dbfn,
                "-n", str(ngram_length),
                "-s", similarity_measure,
                "-t", str(threshold),
                ]
        if self.is_build:
            cmd.append("-b")
        if unicode:
            cmd.append("-u")

        self.proc = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE, encoding="utf-8")
        # TODO use `self.proc.poll()` to check if the process ran into trouble

    def _check_error(self, errs=None):
        if self.proc.returncode:
            if errs is None:
                outs, errs = self.proc.communicate('')
            raise SimstringExecException("Error: simstring invocation: {errs}".format(errs=errs))

    def build(self, strs):
        assert self.is_build, "Error: build on non-build simstring"
        assert self.proc, "Simstring not found"
        instr = ''.join(s + '\n' for s in strs)
        outs, errs = self.proc.communicate(instr)
        self._check_error(errs)
        self.close()

    def insert(self, s):
        assert self.is_build, "Error: build on non-build simstring"
        assert self.proc, "Simstring not found"
        self.proc.stdin.write(s + "\n")
        self._check_error()

    def lookup(self, s):
        if not self.proc:
            return []
        try:
            self.proc.stdin.write(s + "\n")
            self.proc.stdin.flush()
            response = []
            while True:
                line = self.proc.stdout.readline()
                if not line.startswith("\t"):
                    break
                response.append(line.strip())
        except BrokenPipeError:
            message = self.proc.stderr.read()
            self.close()
            raise SimstringExecException(message) from None
        return response

    def close(self):
        if self.proc:
            outs, errs = self.proc.communicate('')
            self.proc = None



if __name__ == "__main__":
    test(SimstringExec)
