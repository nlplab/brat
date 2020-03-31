import simstring
from simstringbase import SimstringBase, test


class SimstringLib(SimstringBase):
    SIMILARITY_MEASURES = {
            "cosine": simstring.cosine,
            "overlap": simstring.overlap,
            }

    def __init__(self, dbfn,
            ngram_length=SimstringBase.DEFAULT_NGRAM_LENGTH,
            include_marks=SimstringBase.DEFAULT_INCLUDE_MARKS,
            threshold=SimstringBase.DEFAULT_THRESHOLD,
            similarity_measure=SimstringBase.DEFAULT_SIMILARITY_MEASURE,
            build=False):

        assert include_marks == False, "Error: begin/end marks not supported"
        assert ngram_length == 3, "Error: unsupported n-gram length"

        dbfn = self.find_db(dbfn, build)
        self.build = build
        if build:
            self.db = simstring.writer(dbfn)
        else:
            self.db = simstring.reader(dbfn)

        self.db.measure = SIMILARITY_MEASURES[similarity_measure]
        self.threshold = threshold
        self.db.threshold = threshold

    def build(self, strs):
        assert self.build, "Error: build on non-build simstring"
        for s in strs:
            self.db.insert(s)
        self.close()

    def lookup(self, s):
        assert not self.build, "Error: lookup on build simstring"
        return self.db.retrieve(s)

    def close(self):
        if self.db:
            self.db.close()
            self.db = None



if __name__ == "__main__":
    test(SimstringLib)
