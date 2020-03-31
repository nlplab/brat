from os.path import sep as path_sep, join as path_join, isfile
import glob
import os
import config

try:
    from config import BASE_DIR, WORK_DIR
except ImportError:
    # for CLI use; assume we're in brat server/src/ and config is in root
    from sys import path as sys_path
    from os.path import dirname
    sys_path.append(path_join(dirname(__file__), '../..'))
    from config import BASE_DIR, WORK_DIR




class SimstringBase:
    class ssdbNotFoundError(Exception):
        def __init__(self, fn):
            self.fn = fn

        def __str__(self):
            return 'Simstring database file "%s" not found' % self.fn

    # Default similarity measure
    DEFAULT_SIMILARITY_MEASURE = 'cosine'

    # Default similarity threshold
    DEFAULT_THRESHOLD = 0.7

    # Length of n-grams in simstring DBs
    DEFAULT_NGRAM_LENGTH = 3

    # Whether to include marks for begins and ends of strings
    DEFAULT_INCLUDE_MARKS = False

    # Whether simstring uses Unicode
    DEFAULT_UNICODE = getattr(config, 'SIMSTRING_DEFAULT_UNICODE', True)

    # Filename extension used for DB file.
    SS_DB_FILENAME_EXTENSION = "ss.db"

    def __init__(self, dbfn,
            ngram_length=DEFAULT_NGRAM_LENGTH,
            include_marks=DEFAULT_INCLUDE_MARKS,
            threshold=DEFAULT_THRESHOLD,
            similarity_measure=DEFAULT_SIMILARITY_MEASURE,
            unicode=DEFAULT_UNICODE,
            build=False):

        self.name = dbfn
        dbfn = self.find_db(dbfn, build)
        self.dbfn = dbfn
        self.threshold = threshold
        self.is_build = build

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @staticmethod
    def find_db(db, missing_ok=False):
        """Given a simstring DB name/path, returns the path for the file that is
        expected to contain the simstring DB."""
        # Assume we have a path relative to the brat root if the value
        # contains a separator, name only otherwise.
        # TODO: better treatment of name / path ambiguity, this doesn't
        # allow e.g. DBs to be located in brat root
        if path_sep in db:
            base = BASE_DIR
        else:
            base = WORK_DIR
        fname = path_join(base, db + '.' + SimstringBase.SS_DB_FILENAME_EXTENSION)
        if not (missing_ok or isfile(fname)):
            raise SimstringBase.ssdbNotFoundError(fname)
        return fname

    def supstring_lookup(self, s, score=False):
        # The simstring overlap measure is symmetric and thus does not
        # differentiate between substring and superstring matches.
        # Replicate a small bit of the simstring functionality (mostly the
        # ngrams() function) to filter to substrings only.
        s_ngrams = ngrams(s)
        result = self.lookup(s)
        filtered = []
        for r in result:
            if s in r:
                # avoid calculation: simple containment => score=1
                if score:
                    filtered.append((r, 1.0))
                else:
                    filtered.append(r)
            else:
                r_ngrams = ngrams(r)
                overlap = s_ngrams & r_ngrams
                if len(overlap) >= len(s_ngrams) * self.threshold:
                    if score:
                        filtered.append((r, 1.0 * len(overlap) / len(s_ngrams)))
                    else:
                        filtered.append(r)

        return filtered

    def delete(self):
        self.close()
        os.remove(self.dbfn)
        for fn in glob.glob(self.dbfn + '.*.cdb'):
            os.remove(fn)


def ngrams(s, out=None, n=SimstringBase.DEFAULT_NGRAM_LENGTH, be=SimstringBase.DEFAULT_INCLUDE_MARKS):
    """Extracts n-grams from the given string s and adds them into the given
    set out (or a new set if None).

    Returns the set. If be is True, affixes begin and end markers to
    strings.
    """

    if out is None:
        out = set()

    # implementation mirroring ngrams() in ngram.h in simstring-1.0
    # distribution.

    mark = '\x01'
    src = ''
    if be:
        # affix begin/end marks
        for i in range(n - 1):
            src += mark
        src += s
        for i in range(n - 1):
            src += mark
    elif len(s) < n:
        # pad strings shorter than n
        src = s
        for i in range(n - len(s)):
            src += mark
    else:
        src = s

    # count n-grams
    stat = {}
    for i in range(len(src) - n + 1):
        ngram = src[i:i + n]
        stat[ngram] = stat.get(ngram, 0) + 1

    # convert into a set
    for ngram, count in list(stat.items()):
        out.add(ngram)
        # add ngram affixed with number if it appears more than once
        for i in range(1, count):
            out.add(ngram + str(i + 1))

    return out



def test(simstringClass):
    # test
    dbname = "TEMP-TEST-DB"
#     strings = [
#         "Cellular tumor antigen p53",
#         "Nucleoporin NUP53",
#         "Tumor protein p53-inducible nuclear protein 2",
#         "p53-induced protein with a death domain",
#         "TP53-regulating kinase",
#         "Tumor suppressor p53-binding protein 1",
#         "p53 apoptosis effector related to PMP-22",
#         "p53 and DNA damage-regulated protein 1",
#         "Tumor protein p53-inducible protein 11",
#         "TP53RK-binding protein",
#         "TP53-regulated inhibitor of apoptosis 1",
#         "Apoptosis-stimulating of p53 protein 2",
#         "Tumor protein p53-inducible nuclear protein 1",
#         "TP53-target gene 1 protein",
#         "Accessory gland protein Acp53Ea",
#         "p53-regulated apoptosis-inducing protein 1",
#         "Tumor protein p53-inducible protein 13",
#         "TP53-target gene 3 protein",
#         "Apoptosis-stimulating of p53 protein 1",
#         "Ribosome biogenesis protein NOP53",
#         ]
    strings = [
        "0",
        "01",
        "012",
        "0123",
        "01234",
        "-12345",
        "012345",
    ]
    print('strings:', strings)

    with simstringClass(dbname, build=True) as ss:
        ss.build(strings)

    with simstringClass(dbname) as ss:
        for t in ['0', '012', '012345', '0123456', '0123456789']:
            print('lookup for', t)
            for s in ss.lookup(t):
                print(s, 'contains', t, '(threshold %f)' % simstringClass.DEFAULT_THRESHOLD)
        ss.delete()
