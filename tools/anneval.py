#!/usr/bin/env python

"""Parse an annotation log and extract annotation statistics.

Author:     Pontus Stenetorp <pontus stenetorp se>
Version:    2011-11-25
"""

from argparse import ArgumentParser
from collections import namedtuple
from datetime import datetime
from sys import stderr

# Constants
ARGPARSER = ArgumentParser()  # XXX:
ARGPARSER.add_argument('ann_log', nargs='+')
###


# TODO: Some arguments left out
LogLine = namedtuple('LogLine', ('time', 'user', 'collection', 'document',
                                 'state', 'action', 'line_no'))


def _parse_log_iter(log):
    for line_no, line in enumerate((l.rstrip('\n') for l in log)):
        date_stamp, time_stamp, user, collection, document, state, action = line.split()[
            :7]
        dtime = datetime.strptime('%s %s' % (date_stamp, time_stamp, ),
                                  '%Y-%m-%d %H:%M:%S,%f')
        yield LogLine(
            time=dtime,
            user=user,
            collection=collection,
            document=document,
            state=state,
            action=action,
            line_no=line_no,
        )


Action = namedtuple('Action', ('start', 'end', 'action'))

# TODO: Give actions and sub actions


def _action_iter(log_lines):
    start_by_action = {}
    for log_line in log_lines:
        #print >> stderr, log_line
        if log_line.state == 'START':
            start_by_action[log_line.action] = log_line
        elif log_line.state == 'FINISH':
            start_line = start_by_action[log_line.action]
            del start_by_action[log_line.action]
            yield Action(start=start_line, end=log_line,
                         action=log_line.action)

# TODO: Log summary object


def main(args):
    argp = ARGPARSER.parse_args(args[1:])

    for ann_log_path in argp.ann_log:
        with open(ann_log_path, 'r') as ann_log:
            log_lines = []
            for log_line in _parse_log_iter(ann_log):
                assert log_line.state in set(
                    ('START', 'FINISH',)), 'unknown logged state'
                log_lines.append(log_line)

        clock_time = log_lines[-1].time - log_lines[0].time
        print('Clock time:', clock_time, file=stderr)
        from datetime import timedelta
        ann_time = timedelta()
        last_span_selected = None
        for action in _action_iter(log_lines):
            if (action.action == 'spanSelected'
                    or action.action == 'spanEditSelected'
                    or action.action == 'suggestSpanTypes'):
                last_span_selected = action

            if action.action == 'createSpan':
                ann_time = ann_time + \
                    (action.end.time - last_span_selected.start.time)
                last_span_selected = None
            # print action
        ann_port_of_clock = float(ann_time.seconds) / clock_time.seconds
        print('Annotation time: %s (portion of clock time: %.1f%%)' % (
            ann_time, ann_port_of_clock * 100, ), file=stderr)


'''
Ordinary sequence:
    * spanSelected
    * createSpan
'''

if __name__ == '__main__':
    from sys import argv
    exit(main(argv))
