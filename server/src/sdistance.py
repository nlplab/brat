#!/usr/bin/env python

"""Various string distance measures.

Author:     Pontus Stenetorp    <pontus stenetorp se>
Version:    2011-08-09
"""

from string import ascii_lowercase as lowercase
from string import digits
from sys import maxsize as maxint

DIGITS = set(digits)
LOWERCASE = set(lowercase)
TSURUOKA_2004_INS_CHEAP = set((' ', '-', ))
TSURUOKA_2004_DEL_CHEAP = TSURUOKA_2004_INS_CHEAP
TSURUOKA_2004_REPL_CHEAP = set([(a, b) for a in DIGITS for b in DIGITS] +
                               [(a, a.upper()) for a in LOWERCASE] +
                               [(a.upper(), a) for a in LOWERCASE] +
                               [(' ', '-'), ('-', '_')])
# Testing; not sure number replacements should be cheap.
NONNUM_T2004_REPL_CHEAP = set([(a, a.upper()) for a in LOWERCASE] +
                              [(a.upper(), a) for a in LOWERCASE] +
                              [(' ', '-'), ('-', '_')])

TSURUOKA_INS = dict([(c, 10) for c in TSURUOKA_2004_INS_CHEAP])
TSURUOKA_DEL = dict([(c, 10) for c in TSURUOKA_2004_DEL_CHEAP])
# TSURUOKA_REPL = dict([(c, 10) for c in TSURUOKA_2004_REPL_CHEAP])
TSURUOKA_REPL = dict([(c, 10) for c in NONNUM_T2004_REPL_CHEAP])


def tsuruoka(a, b):
    # Special case for empties
    if len(a) == 0 or len(b) == 0:
        return 100 * max(len(a), len(b))

    # Initialise the first column
    prev_min_col = [0]
    for b_c in b:
        prev_min_col.append(prev_min_col[-1] + TSURUOKA_INS.get(b_c, 100))
    curr_min_col = prev_min_col

    for a_c in a:
        curr_min_col = [prev_min_col[0] + TSURUOKA_DEL.get(a_c, 100)]

        for b_i, b_c in enumerate(b):
            if b_c == a_c:
                curr_min_col.append(prev_min_col[b_i])
            else:
                curr_min_col.append(min(
                    prev_min_col[b_i + 1] + TSURUOKA_DEL.get(a_c, 100),
                    curr_min_col[-1] + TSURUOKA_INS.get(b_c, 100),
                    prev_min_col[b_i] + TSURUOKA_REPL.get((a_c, b_c), 50)
                ))

        prev_min_col = curr_min_col

    return curr_min_col[-1]


def tsuruoka_local(a, b, edge_insert_cost=1, max_cost=maxint):
    # Variant of the tsuruoka metric for local (substring) alignment:
    # penalizes initial or final insertion for a by a different
    # (normally small or zero) cost than middle insertion.
    # If the current cost at any point exceeds max_cost, returns
    # max_cost, which may allow early return.

    # Special cases for empties
    if len(a) == 0:
        return len(b) * edge_insert_cost
    if len(b) == 0:
        return 100 * len(b)

    # Shortcut: strict containment
    if a in b:
        cost = (len(b) - len(a)) * edge_insert_cost
        return cost if cost < max_cost else max_cost

    # Initialise the first column. Any sequence of initial inserts
    # have edge_insert_cost.
    prev_min_col = [0]
    for b_c in b:
        prev_min_col.append(prev_min_col[-1] + edge_insert_cost)
    curr_min_col = prev_min_col

    for a_c in a:
        curr_min_col = [prev_min_col[0] + TSURUOKA_DEL.get(a_c, 100)]

        for b_i, b_c in enumerate(b):
            if b_c == a_c:
                curr_min_col.append(prev_min_col[b_i])
            else:
                curr_min_col.append(min(
                    prev_min_col[b_i + 1] + TSURUOKA_DEL.get(a_c, 100),
                    curr_min_col[-1] + TSURUOKA_INS.get(b_c, 100),
                    prev_min_col[b_i] + TSURUOKA_REPL.get((a_c, b_c), 50)
                ))

        # early return
        if min(curr_min_col) >= max_cost:
            return max_cost

        prev_min_col = curr_min_col

    # Any number of trailing inserts have edge_insert_cost
    min_cost = curr_min_col[-1]
    for i in range(len(curr_min_col)):
        cost = curr_min_col[i] + edge_insert_cost * (len(curr_min_col) - i - 1)
        min_cost = min(min_cost, cost)

    if min_cost < max_cost:
        return min_cost
    else:
        return max_cost


def tsuruoka_norm(a, b):
    return 1 - (tsuruoka(a, b) / (max(len(a), len(b)) * 100.))


def levenshtein(a, b):
    # Special case for empties
    if len(a) == 0 or len(b) == 0:
        return max(len(a), len(b))

    # Initialise the first column
    prev_min_col = [0]
    for b_c in b:
        prev_min_col.append(prev_min_col[-1] + 1)
    curr_min_col = prev_min_col

    for a_c in a:
        curr_min_col = [prev_min_col[0] + 1]

        for b_i, b_c in enumerate(b):
            if b_c == a_c:
                curr_min_col.append(prev_min_col[b_i])
            else:
                curr_min_col.append(min(
                    prev_min_col[b_i + 1] + 1,
                    curr_min_col[-1] + 1,
                    prev_min_col[b_i] + 1
                ))

        prev_min_col = curr_min_col

    return curr_min_col[-1]


if __name__ == '__main__':
    for a, b in (('kitten', 'sitting'), ('Saturday', 'Sunday'), ('Caps', 'caps'),
                 ('', 'bar'), ('dog', 'dog'), ('dog', '___dog__'), ('dog', '__d_o_g__')):
        print('levenshtein', a, b, levenshtein(a, b))
        print('tsuruoka', a, b, tsuruoka(a, b))
        print('tsuruoka_local', a, b, tsuruoka_local(a, b))
        print('tsuruoka_norm', a, b, tsuruoka_norm(a, b))
