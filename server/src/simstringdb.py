#!/usr/bin/env python

import glob
import os
import sys
from os.path import join as path_join
from os.path import sep as path_sep

from common import ProtocolError
from message import Messager

try:
    from config import BASE_DIR, WORK_DIR
except ImportError:
    # for CLI use; assume we're in brat server/src/ and config is in root
    from sys import path as sys_path
    from os.path import dirname
    sys_path.append(path_join(dirname(__file__), '../..'))
    from config import BASE_DIR, WORK_DIR

# Default filename extension of the SQL database
SQL_DB_FILENAME_EXTENSION = 'db'

# Filename extension used for DB file.
SS_DB_FILENAME_EXTENSION = 'ss.db'

# Default similarity measure
DEFAULT_SIMILARITY_MEASURE = 'cosine'

# Default similarity threshold
DEFAULT_THRESHOLD = 0.7

# Length of n-grams in simstring DBs
DEFAULT_NGRAM_LENGTH = 3

# Whether to include marks for begins and ends of strings
DEFAULT_INCLUDE_MARKS = False

SIMSTRING_MISSING_ERROR = '''Error: failed to import the simstring library.
This library is required for approximate string matching DB lookup.
Please install simstring and its Python bindings from
http://www.chokkan.org/software/simstring/'''


class NoSimStringError(ProtocolError):
    def __str__(self):
        return ('No SimString bindings found, please install them from: '
                'http://www.chokkan.org/software/simstring/')

    def json(self, json_dic):
        json_dic['exception'] = 'noSimStringError'


class ssdbNotFoundError(Exception):
    def __init__(self, fn):
        self.fn = fn

    def __str__(self):
        return 'Simstring database file "%s" not found' % self.fn

# Note: The only reason we use a function call for this is to delay the import

def __import_simstring():
    global SIMSTRING_BINARY
    try:
        import simstring
    except ImportError:
        Messager.error(SIMSTRING_MISSING_ERROR, duration=-1)
        raise NoSimStringError
    # Distinguish original simstring from simstring-pure
    SIMSTRING_BINARY = hasattr(simstring, 'writer')

    if not SIMSTRING_BINARY:
        global SQLite3Database, CharacterNgramFeatureExtractor, CosineMeasure, OverlapMeasure, Searcher
        from simstring_pure_sqlite3 import SQLite3Database
        from simstring.feature_extractor.character_ngram import CharacterNgramFeatureExtractor
        from simstring.measure.cosine import CosineMeasure
        from simstring_pure_overlap import OverlapMeasure
        from simstring.searcher import Searcher


def __set_db_measure(db, measure):
    __import_simstring()
    ss_measure_by_str = {
        'cosine': simstring.cosine,
        'overlap': simstring.overlap,
    }
    db.measure = ss_measure_by_str[measure]


def __ssdb_path(db):
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
    extension = SS_DB_FILENAME_EXTENSION if SIMSTRING_BINARY else SQL_DB_FILENAME_EXTENSION
    return path_join(base, db + '.' + extension)


def ssdb_build(strs, dbname, ngram_length=DEFAULT_NGRAM_LENGTH,
               include_marks=DEFAULT_INCLUDE_MARKS):
    """Given a list of strings, a DB name, and simstring options, builds a
    simstring DB for the strings."""
    __import_simstring()
    dbfn = __ssdb_path(dbname)
    try:
        # only library defaults (n=3, no marks) supported just now (TODO)
        assert include_marks == False, "Error: begin/end marks not supported"
        if SIMSTRING_BINARY:
            assert ngram_length == 3, "Error: unsupported n-gram length"
            db = simstring.writer(dbfn)
            for s in strs:
                db.insert(s)
            db.close()
        else:
            fx = CharacterNgramFeatureExtractor(DEFAULT_NGRAM_LENGTH)
            db = SQLite3Database(fx)
            db.use(dbfn)
            for s in strs:
                db.add(s)

    except BaseException:
        print >> sys.stderr, "Error building simstring DB"
        raise

    return dbfn


def ssdb_delete(dbname):
    """Given a DB name, deletes all files associated with the simstring DB."""

    dbfn = __ssdb_path(dbname)
    os.remove(dbfn)
    for fn in glob.glob(dbfn + '.*.cdb'):
        os.remove(fn)


def ssdb_open(dbname):
    """Given a DB name, opens it as a simstring DB and returns the handle.

    The caller is responsible for invoking close() on the handle.
    """
    __import_simstring()

    try:
        if SIMSTRING_BINARY:
            return simstring.reader(__ssdb_path(dbname))
        else:
            fx = CharacterNgramFeatureExtractor(DEFAULT_NGRAM_LENGTH)
            db = SQLite3Database(fx)
            return db.use(__ssdb_path(dbname))
    except IOError:
        Messager.error('Failed to open simstring DB %s' % dbname)
        raise ssdbNotFoundError(dbname)


def ssdb_lookup(s, dbname, measure=DEFAULT_SIMILARITY_MEASURE,
                threshold=DEFAULT_THRESHOLD):
    """Given a string and a DB name, returns the strings matching in the
    associated simstring DB."""
    db = ssdb_open(dbname)

    if SIMSTRING_BINARY:
        __set_db_measure(db, measure)
        db.threshold = threshold

        result = db.retrieve(s)
    else:
        searcher = Searcher(db, __get_pure_measure(measure))
        result = searcher.search(s, threshold)

    db.close()
    return result


def ngrams(s, out=None, n=DEFAULT_NGRAM_LENGTH, be=DEFAULT_INCLUDE_MARKS):
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


def ssdb_supstring_lookup(s, dbname, threshold=DEFAULT_THRESHOLD,
                          with_score=False):
    """Given a string s and a DB name, returns the strings in the associated
    simstring DB that likely contain s as an (approximate) substring.

    If with_score is True, returns pairs of (str,score) where score is
    the fraction of n-grams in s that are also found in the matched
    string.
    """
    db = ssdb_open(dbname)
    if SIMSTRING_BINARY:
        __set_db_measure(db, 'overlap')
        db.threshold = threshold

        result = db.retrieve(s)
    else:
        searcher = Searcher(db, OverlapMeasure())
        result = searcher.search(s, threshold)
    db.close()

    # The simstring overlap measure is symmetric and thus does not
    # differentiate between substring and superstring matches.
    # Replicate a small bit of the simstring functionality (mostly the
    # ngrams() function) to filter to substrings only.
    s_ngrams = ngrams(s)
    filtered = []
    for r in result:
        if s in r:
            # avoid calculation: simple containment => score=1
            if with_score:
                filtered.append((r, 1.0))
            else:
                filtered.append(r)
        else:
            r_ngrams = ngrams(r)
            overlap = s_ngrams & r_ngrams
            if len(overlap) >= len(s_ngrams) * threshold:
                if with_score:
                    filtered.append((r, 1.0 * len(overlap) / len(s_ngrams)))
                else:
                    filtered.append(r)

    return filtered


def ssdb_supstring_exists(s, dbname, threshold=DEFAULT_THRESHOLD):
    """Given a string s and a DB name, returns whether at least one string in
    the associated simstring DB likely contains s as an (approximate)
    substring."""

    if threshold == 1.0:
        # optimized (not hugely, though) for this common case
        __import_simstring()
        db = ssdb_open(dbname)

        if SIMSTRING_BINARY:
            __set_db_measure(db, 'overlap')
            db.threshold = threshold

            result = db.retrieve(s)
        else:
            searcher = Searcher(db, OverlapMeasure())
            result = searcher.search(s, threshold)

        db.close()

        for r in result:
            if s in r:
                return True
        return False
    else:
        # naive implementation for everything else
        return len(ssdb_supstring_lookup(s, dbname, threshold)) != 0


if __name__ == "__main__":
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
    ssdb_build(strings, dbname)
    for t in ['0', '012', '012345', '0123456', '0123456789']:
        print('lookup for', t)
        for s in ssdb_supstring_lookup(t, dbname):
            print(s, 'contains', t, '(threshold %f)' % DEFAULT_THRESHOLD)
    ssdb_delete(dbname)
