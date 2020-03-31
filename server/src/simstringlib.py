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
            unicode=SimstringBase.DEFAULT_UNICODE,
            build=False):

        assert include_marks == False, "Error: begin/end marks not supported"
        assert ngram_length == 3, "Error: unsupported n-gram length"

        super().__init__(dbfn,
                ngram_length=ngram_length,
                include_marks=include_marks,
                threshold=threshold,
                similarity_measure=similarity_measure,
                unicode=unicode,
                build=build)

        if build:
            self.db = simstring.writer(self.dbfn)
        else:
            self.db = simstring.reader(self.dbfn)

        self.db.measure = SIMILARITY_MEASURES[similarity_measure]
        self.db.threshold = threshold

    def build(self, strs):
        for s in strs:
            self.insert(s)
        self.close()

    def insert(self, s):
        assert self.build, "Error: build on non-build simstring"
        self.db.insert(s)

    def lookup(self, s):
        assert not self.build, "Error: lookup on build simstring"
        return self.db.retrieve(s)

    def close(self):
        if self.db:
            self.db.close()
            self.db = None



if __name__ == "__main__":
    test(SimstringLib)
