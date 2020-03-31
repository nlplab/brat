from subprocess import Popen, PIPE, run
from simstringbase import SimstringBase, test


# make sure the simstring executable can be run
assert not run(["which", "simstring"], capture_output=True).returncode, "Error: simstring not found"


class SimstringExecException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return 'Simstring error: %s' % self.message


class SimstringExec(SimstringBase):
    SS_EXECUTABLE = "simstring"

    def __init__(self, dbfn,
            ngram_length=SimstringBase.DEFAULT_NGRAM_LENGTH,
            include_marks=SimstringBase.DEFAULT_INCLUDE_MARKS,
            threshold=SimstringBase.DEFAULT_THRESHOLD,
            similarity_measure=SimstringBase.DEFAULT_SIMILARITY_MEASURE,
            build=False,
            unicode=True):

        dbfn = self.find_db(dbfn, build)
        cmd = [SimstringExec.SS_EXECUTABLE,
                "-d", dbfn,
                "-n", str(ngram_length),
                "-s", similarity_measure,
                "-t", str(threshold),
                ]
        self.is_build = build
        if build:
            cmd.append("-b")
        if unicode:
            cmd.append("-u")

        self.dbfn = dbfn
        self.threshold = threshold
        self.proc = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE, encoding="utf-8")

    def build(self, strs):
        assert self.is_build, "Error: build on non-build simstring"
        instr = ''.join(s + '\n' for s in strs)
        outs, errs = self.proc.communicate(instr)
        assert not self.proc.returncode, "Error: simstring invocation: {errs}".format(errs=errs)
        self.close()

    def lookup(self, s):
        assert not self.is_build, "Error: lookup on build simstring"
        try:
            self.proc.stdin.write(s + '\n')
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
            self.proc.terminate()
            self.proc = None



if __name__ == "__main__":
    test(SimstringExec)
