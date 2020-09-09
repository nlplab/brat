#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

"""Normalization support."""

from datetime import datetime
from functools import reduce

import normdb
import sdistance
from simstringdb import Simstring
from document import real_directory
from message import Messager
from normdb import string_norm_form
from projectconfig import ProjectConfiguration

# whether to display alignment scores in search result table
DISPLAY_SEARCH_SCORES = False

# maximum alignment score (tsuruoka_local)
MAX_SCORE = 1000

# maximum alignment score (tsuruoka_local) difference allowed between
# the score for a string s and the best known score before excluding s
# from consideration
MAX_DIFF_TO_BEST_SCORE = 200

# maximum number of search results to return
MAX_SEARCH_RESULT_NUMBER = 1000

NORM_LOOKUP_DEBUG = True

REPORT_LOOKUP_TIMINGS = False

# debugging


def _check_DB_version(database):
    # TODO; not implemented yet for new-style SQL DBs.
    pass


def _report_timings(dbname, start, msg=None):
    delta = datetime.now() - start
    strdelta = str(delta).replace('0:00:0', '')  # take out zero min & hour
    queries = normdb.get_query_count(dbname)
    normdb.reset_query_count(dbname)
    Messager.info("Processed " + str(queries) + " queries in " + strdelta +
                  (msg if msg is not None else ""))


def _get_db_path(database, collection):
    if collection is None:
        # TODO: default to WORK_DIR config?
        return (None, Simstring.DEFAULT_UNICODE)
    else:
        try:
            conf_dir = real_directory(collection)
            projectconf = ProjectConfiguration(conf_dir)
            norm_conf = projectconf.get_normalization_config()
            for entry in norm_conf:
                # TODO THIS IS WRONG
                dbname, dbpath, dbunicode = entry[0], entry[3], entry[4]
                if dbname == database:
                    return (dbpath, dbunicode)
            # not found in config.
            Messager.warning('DB ' + database + ' not defined in config for ' +
                             collection + ', falling back on default.')
            return (None, Simstring.DEFAULT_UNICODE)
        except Exception:
            # whatever goes wrong, just warn and fall back on the default.
            Messager.warning('Failed to get DB path from config for ' +
                             collection + ', falling back on default.')
            return (None, Simstring.DEFAULT_UNICODE)


def norm_get_name(database, key, collection=None):
    if NORM_LOOKUP_DEBUG:
        _check_DB_version(database)
    if REPORT_LOOKUP_TIMINGS:
        lookup_start = datetime.now()

    dbpath, dbunicode = _get_db_path(database, collection)
    if dbpath is None:
        # full path not configured, fall back on name as default
        dbpath = database

    try:
        data = normdb.data_by_id(dbpath, key)
    except normdb.dbNotFoundError as e:
        Messager.warning(str(e))
        data = None

    # just grab the first one (sorry, this is a bit opaque)
    if data is not None:
        value = data[0][0][1]
    else:
        value = None

    if REPORT_LOOKUP_TIMINGS:
        _report_timings(database, lookup_start)

    # echo request for sync
    json_dic = {
        'database': database,
        'key': key,
        'value': value
    }
    return json_dic


def norm_get_data(database, key, collection=None):
    if NORM_LOOKUP_DEBUG:
        _check_DB_version(database)
    if REPORT_LOOKUP_TIMINGS:
        lookup_start = datetime.now()

    dbpath, dbunicode = _get_db_path(database, collection)
    if dbpath is None:
        # full path not configured, fall back on name as default
        dbpath = database

    try:
        data = normdb.data_by_id(dbpath, key)
    except normdb.dbNotFoundError as e:
        Messager.warning(str(e))
        data = None

    if data is None:
        Messager.warning("Failed to get data for " + database + ":" + key)

    if REPORT_LOOKUP_TIMINGS:
        _report_timings(database, lookup_start)

    # echo request for sync
    json_dic = {
        'database': database,
        'key': key,
        'value': data
    }
    return json_dic

# TODO: deprecated, confirm unnecessary and remove.
# def norm_get_ids(database, name, collection=None):
#     if NORM_LOOKUP_DEBUG:
#         _check_DB_version(database)
#     if REPORT_LOOKUP_TIMINGS:
#         lookup_start = datetime.now()
#
#     dbpath, dbunicode = _get_db_path(database, collection)
#     if dbpath is None:
#         # full path not configured, fall back on name as default
#         dbpath = database
#
#     keys = normdb.ids_by_name(dbpath, name)
#
#     if REPORT_LOOKUP_TIMINGS:
#         _report_timings(database, lookup_start)
#
#     # echo request for sync
#     json_dic = {
#         'database' : database,
#         'value' : name,
#         'keys' : keys,
#         }
#     return json_dic


def _format_datas(datas, scores=None, matched=None):
    # helper for norm_search(), formats data from DB into a table
    # for client, sort by scores if given.

    if scores is None:
        scores = {}
    if matched is None:
        matched = {}

    # chop off all but the first two groups of label:value pairs for
    # each key; latter ones are assumed to be additional information
    # not intended for display of search results.
    # TODO: avoid the unnecessary queries for this information.
    cropped = {}
    for key in datas:
        cropped[key] = datas[key][:2]
    datas = cropped

    # organize into a table format with separate header and data
    # (this matches the collection browser data format)
    unique_labels = []
    seen_label = {}
    for key in datas:
        # check for dups within each entry
        seen_label_for_key = {}
        for i, group in enumerate(datas[key]):
            for label, value in group:
                if label not in seen_label:
                    # store with group index to sort all labels by
                    # group idx first
                    unique_labels.append((i, label))
                seen_label[label] = True
                if label in seen_label_for_key:
                    # too noisy, and not really harmful now that matching
                    # values are preferred for repeated labels.
                    #                     Messager.warning("Repeated label (%s) in normalization data not supported" % label)
                    pass
                seen_label_for_key[label] = True

    # sort unique labels by group index (should be otherwise stable,
    # holds since python 2.3), and flatten
    unique_labels.sort(key=lambda a: a[0])
    unique_labels = [a[1] for a in unique_labels]

    # ID is first field, and datatype is "string" for all labels
    header = [(label, "string") for label in ["ID"] + unique_labels]

    if DISPLAY_SEARCH_SCORES:
        header += [("score", "int")]

    # construct items, sorted by score first, ID second (latter for stability)
    sorted_keys = sorted(list(datas.keys()), key=lambda a: (scores.get(a, 0), a), reverse=True)

    items = []
    for key in sorted_keys:
        # make dict for lookup. In case of duplicates (e.g. multiple
        # "synonym" entries), prefer ones that were matched.
        # TODO: prefer more exact matches when multiple found.
        data_dict = {}
        for group in datas[key]:
            for label, value in group:
                if label not in data_dict or (value in matched and
                                              data_dict[label] not in matched):
                    data_dict[label] = value
        # construct item
        item = [str(key)]
        for label in unique_labels:
            if label in data_dict:
                item.append(data_dict[label])
            else:
                item.append('')

        if DISPLAY_SEARCH_SCORES:
            item += [str(scores.get(key))]

        items.append(item)

    return header, items


def _norm_filter_score(score, best_score=MAX_SCORE):
    return score < best_score - MAX_DIFF_TO_BEST_SCORE

# TODO: get rid of arbitrary max_cost default constant


def _norm_score(substring, name, max_cost=500):
    # returns an integer score representing the similarity of the given
    # substring to the given name (larger is better).
    cache = _norm_score.__cache
    if (substring, name) not in cache:
        cost = sdistance.tsuruoka_local(substring, name, max_cost=max_cost)
        # debugging
        #Messager.info('%s --- %s: %d (max %d)' % (substring, name, cost, max_cost))
        score = MAX_SCORE - cost
        cache[(substring, name)] = score
    # TODO: should we avoid exceeding max_cost? Cached values might.
    return cache[(substring, name)]


_norm_score.__cache = {}


def _norm_search_name_attr(ss, name, attr,
                           matched, score_by_id, score_by_str,
                           best_score=0, exactmatch=False):
    # helper for norm_search, searches for matches where given name
    # appears either in full or as an approximate substring of a full
    # name (if exactmatch is False) in given DB. If attr is not None,
    # requires its value to appear as an attribute of the entry with
    # the matched name. Updates matched, score_by_id, and
    # score_by_str, returns best_score.

    # If there are no strict substring matches for a given attribute
    # in the simstring DB, we can be sure that no query can succeed,
    # and can fail early.
    # TODO: this would be more effective (as would some other things)
    # if the attributes were in a separate simstring DB from the
    # names.
    if attr is not None:
        normattr = string_norm_form(attr)
        if not ss.supstring_lookup(normattr):
            # debugging
            #Messager.info('Early norm search fail on "%s"' % attr)
            return best_score

    if exactmatch:
        # only candidate string is given name
        strs = [name]
        ss_norm_score = {string_norm_form(name): 1.0}
    else:
        # expand to substrings using simstring
        # simstring requires UTF-8
        normname = string_norm_form(name)
        str_scores = ss.supstring_lookup(normname, True)
        strs = [s[0] for s in str_scores]
        ss_norm_score = dict(str_scores)

        # TODO: recreate this older filter; watch out for which name to use!
#         # filter to strings not already considered
#         strs = [s for s in strs if (normname, s) not in score_by_str]

    # look up IDs
    if attr is None:
        id_names = normdb.ids_by_names(ss.name, strs, False, True)
    else:
        id_names = normdb.ids_by_names_attr(ss.name, strs, attr, False, True)

    # sort by simstring (n-gram overlap) score to prioritize likely
    # good hits.
    # TODO: this doesn't seem to be having a very significant effect.
    # consider removing as unnecessary complication (ss_norm_score also).
    id_name_scores = [(i, n, ss_norm_score[string_norm_form(n)])
                      for i, n in id_names]
    id_name_scores.sort(key=lambda a: a[2], reverse=True)
    id_names = [(i, n) for i, n, s in id_name_scores]

    # update matches and scores
    for i, n in id_names:
        if n not in matched:
            matched[n] = set()
        matched[n].add(i)

        max_cost = MAX_SCORE - best_score + MAX_DIFF_TO_BEST_SCORE + 1
        if (name, n) not in score_by_str:
            # TODO: decide whether to use normalized or unnormalized strings
            # for scoring here.
            #score_by_str[(name, n)] = _norm_score(name, n, max_cost)
            score_by_str[(name, n)] = _norm_score(
                string_norm_form(name), string_norm_form(n), max_cost)
        score = score_by_str[(name, n)]
        best_score = max(score, best_score)

        score_by_id[i] = max(score_by_id.get(i, -1),
                             score_by_str[(name, n)])

        # stop if max count reached
        if len(score_by_id) > MAX_SEARCH_RESULT_NUMBER:
            Messager.info(
                'Note: more than %d search results, only retrieving top matches' %
                MAX_SEARCH_RESULT_NUMBER)
            break

    return best_score


def _norm_search_impl(database, name, collection=None, exactmatch=False):
    if NORM_LOOKUP_DEBUG:
        _check_DB_version(database)
    if REPORT_LOOKUP_TIMINGS:
        lookup_start = datetime.now()

    dbpath, dbunicode = _get_db_path(database, collection)
    if dbpath is None:
        # full path not configured, fall back on name as default
        dbpath = database


    # maintain map from searched names to matching IDs and scores for
    # ranking
    matched = {}
    score_by_id = {}
    score_by_str = {}

    with Simstring(dbpath, unicode=dbunicode) as ss:

        # look up hits where name appears in full
        best_score = _norm_search_name_attr(ss, name, None,
                                            matched, score_by_id, score_by_str,
                                            0, exactmatch)

        # if there are no hits and we only have a simple candidate string,
        # look up with a low threshold
        if best_score == 0 and len(name.split()) == 1:
            with Simstring(dbpath, threshold=0.5, unicode=dbunicode) as low_threshold_ss:
                best_score = _norm_search_name_attr(low_threshold_ss, name, None,
                                                    matched, score_by_id, score_by_str,
                                                    0, exactmatch)

        # if there are no good hits, also consider only part of the input
        # as name and the rest as an attribute.
        # TODO: reconsider arbitrary cutoff
        if best_score < 900 and not exactmatch:
            parts = name.split()

            # prioritize having the attribute after the name
            for i in range(len(parts) - 1, 0, -1):
                # TODO: this early termination is sub-optimal: it's not
                # possible to know in advance which way of splitting the
                # query into parts yields best results. Reconsider.
                if len(score_by_id) > MAX_SEARCH_RESULT_NUMBER:
                    break

                start = ' '.join(parts[:i])
                end = ' '.join(parts[i:])

                # query both ways (start is name, end is attr and vice versa)
                best_score = _norm_search_name_attr(ss, start, end,
                                                    matched, score_by_id,
                                                    score_by_str,
                                                    best_score, exactmatch)
                best_score = _norm_search_name_attr(ss, end, start,
                                                    matched, score_by_id,
                                                    score_by_str,
                                                    best_score, exactmatch)

        # flatten to single set of IDs
        ids = reduce(set.union, list(matched.values()), set())

        # filter ids that now (after all queries complete) fail
        # TODO: are we sure that this is a good idea?
        ids = set([i for i in ids
                if not _norm_filter_score(score_by_id[i], best_score)])

        # TODO: avoid unnecessary queries: datas_by_ids queries for names,
        # attributes and infos, but _format_datas only uses the first two.
        datas = normdb.datas_by_ids(dbpath, ids)

        header, items = _format_datas(datas, score_by_id, matched)

    if REPORT_LOOKUP_TIMINGS:
        _report_timings(database, lookup_start,
                        ", retrieved " + str(len(items)) + " items")

    # echo request for sync
    json_dic = {
        'database': database,
        'query': name,
        'header': header,
        'items': items,
    }
    return json_dic


def norm_search(database, name, collection=None, exactmatch=False):
    try:
        return _norm_search_impl(database, name, collection, exactmatch)
    except Simstring.ssdbNotFoundError as e:
        Messager.warning(str(e))
        return {
            'database': database,
            'query': name,
            'header': [],
            'items': []
        }


def _test():
    # test
    test_cases = {
        'UniProt': {
            'Runx3': 'Q64131',
            'Runx3 mouse': 'Q64131',
            'Runx1': 'Q03347',
            'Runx1 mouse': 'Q03347',
            'Eomes': 'O54839',
            'Eomes mouse': 'O54839',
            'granzyme B': 'P04187',
            'granzyme B mouse': 'P04187',
            'INF-gamma': 'P01580',
            'INF-gamma mouse': 'P01580',
            'IL-2': 'P04351',
            'IL-2 mouse': 'P04351',
            'T-bet': 'Q9JKD8',
            'T-bet mouse': 'Q9JKD8',
            'GATA-1': 'P15976',
            'GATA-1 human': 'P15976',
            'Interleukin-10': 'P22301',
            'Interleukin-10 human': 'P22301',
            'Interleukin-12': 'P29459',
            'Interleukin-12 human': 'P29459',
            'interferon-gamma': 'P01579',
            'interferon-gamma human': 'P01579',
            'interferon gamma human': 'P01579',
            'Fas ligand': 'P48023',
            'Fas ligand human': 'P48023',
            'IkappaB-alpha': 'P25963',
            'IkappaB-alpha human': 'P25963',
            'transforming growth factor (TGF)-beta1': 'P01137',
            'transforming growth factor (TGF)-beta1 human': 'P01137',
            'transforming growth factor beta1 human': 'P01137',
            'tumor necrosis factor alpha': 'P01375',
            'tumor necrosis factor alpha human': 'P01375',
            'Epstein-Barr virus latent membrane protein LMP1': 'Q1HVB3',
            'TATA box binding protein': 'P20226',
            'TATA box binding protein human': 'P20226',
            'HIV protease': '??????',  # TODO
            # TODO
            'human immunodeficiency virus type 1 (HIV) protease': '??????',
        }
    }

    overall_start = datetime.now()
    query_count, hit_count = 0, 0
    misses = []
    for DB in test_cases:
        for query in test_cases[DB]:
            target = test_cases[DB][query]
            start = datetime.now()
            results = norm_search(DB, query)
            delta = datetime.now() - start
            found = False
            found_rank = -1
            for rank, item in enumerate(results['items']):
                id_ = item[0]
                if id_ == target:
                    found = True
                    found_rank = rank + 1
                    break
            strdelta = str(delta).replace('0:00:0', '').replace('0:00:', '')
            print("%s: '%s' <- '%s' rank %d/%d (%s sec)" % ('  ok' if found
                                                            else 'MISS',
                                                            target, query,
                                                            found_rank,
                                                            len(results['items']),
                                                            strdelta))
            query_count += 1
            if found:
                hit_count += 1
            else:
                misses.append((query, target))

    if len(misses) != 0:
        print()
        print("MISSED:")
        for query, target in misses:
            print("%s '%s'" % (target, query))

    delta = datetime.now() - overall_start
    strdelta = str(delta).replace('0:00:0', '').replace('0:00:', '')
    print()
    print("Found %d / %d in %s" % (hit_count, query_count, strdelta))


def _profile_test():
    # runs _test() with profiling, storing results in "norm.profile".
    # To see a profile, run e.g.
    # python -c 'import pstats;
    # pstats.Stats("norm.profile").strip_dirs().sort_stats("time").print_stats()'
    # | less
    import cProfile
    cProfile.run('_test()', 'norm.profile')


if __name__ == '__main__':
    _test()  # normal
    # _profile_test() # profiled
