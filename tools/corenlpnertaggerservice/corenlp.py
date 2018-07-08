#!/usr/bin/env python

"""Using pexpect to interact with CoreNLP.

Author:     Pontus Stenetorp    <pontus stenetorp se>
Version:    2012-04-18
"""

from os import listdir
from os.path import join as path_join
from os.path import isdir
from re import compile as re_compile
from re import match

# I am not a huge fan of pexpect, but it will get the job done
from pexpect import spawn

# Constants
SENTENCE_OUTPUT_REGEX = re_compile(r'Sentence #[0-9]+ \([0-9]+ tokens\):')
OUTPUT_TOKEN_REGEX = re_compile(
    r' CharacterOffsetBegin=(?P<start>[0-9]+).*'
    r' CharacterOffsetEnd=(?P<end>[0-9]+).*'
    r' NamedEntityTag=(?P<type>[^ \]]+)'
)
###

# Handle the interaction and hold the CoreNLP tagging process


class CoreNLPTagger(object):
    def __init__(self, core_nlp_path, mem='1024m'):
        assert isdir(core_nlp_path)
        # Try locating the JAR;s we need
        jar_paths = []
        for jar_regex in (
                '^stanford-corenlp-[0-9]{4}-[0-9]{2}-[0-9]{2}\.jar$',
                '^stanford-corenlp-[0-9]{4}-[0-9]{2}-[0-9]{2}-models\.jar$',
                '^joda-time\.jar$',
                '^xom\.jar$',
        ):
            for fname in listdir(core_nlp_path):
                if match(jar_regex, fname):
                    jar_paths.append(path_join(core_nlp_path, fname))
                    break
            else:
                assert False, 'could not locate any jar on the form "%s"' % jar_regex

        # Then hook up the CoreNLP process
        corenlp_cmd = ' '.join(('java -Xmx%s' % mem,
                                '-cp %s' % ':'.join(jar_paths),
                                'edu.stanford.nlp.pipeline.StanfordCoreNLP',
                                '-annotators tokenize,ssplit,pos,lemma,ner',
                                ))

        # Spawn the process
        self._core_nlp_process = spawn(corenlp_cmd, timeout=600)
        # Wait for the models to load, this is not overly fast
        self._core_nlp_process.expect('Entering interactive shell.')

    def __del__(self):
        # If our child process is still around, kill it
        if self._core_nlp_process.isalive():
            self._core_nlp_process.terminate()

    def tag(self, text):
        self._core_nlp_process.sendline(
            # Newlines are not healthy at this stage, remove them, they
            #   won't affect the offsets
            text.replace('\n', ' ')
        )

        # We can expect CoreNLP to be fairly fast, but let's cut it some slack
        #   half a second per "token" with a start-up of one second
        output_timeout = 1 + int(len(text.split()) * 0.5)
        # Make sure the data was actually seen by CoreNLP
        self._core_nlp_process.expect(SENTENCE_OUTPUT_REGEX,
                                      timeout=output_timeout)
        # Wait or the final results to arrive
        self._core_nlp_process.expect('NLP>', timeout=output_timeout)

        annotations = {}

        def _add_ann(start, end, _type):
            annotations[len(annotations)] = {
                'type': _type,
                'offsets': ((start, end), ),
                'texts': ((text[start:end]), ),
            }

        # Collect the NER spans, CoreNLP appears to be using only a BO tag-set
        #   so parsing it is piece of cake
        for sent_output in (d.strip() for i, d in enumerate(
                self._core_nlp_process.before.rstrip().split('\r\n'))
                if (i + 1) % 3 == 0):
            ann_start = None
            last_end = None
            ann_type = None
            for output_token in sent_output.split('] ['):
                # print ann_start, last_end, ann_type

                # print output_token #XXX:
                m = OUTPUT_TOKEN_REGEX.search(output_token)
                assert m is not None, 'failed to parse output'
                # print m.groupdict() #XXX:

                gdic = m.groupdict()
                start = int(gdic['start'])
                end = int(gdic['end'])
                _type = gdic['type']

                # Have we exited an annotation or changed type?
                if ((_type == 'O' or ann_type != _type)
                        and ann_start is not None):
                    _add_ann(ann_start, last_end, ann_type)
                    ann_start = None
                    ann_type = None
                elif _type != 'O' and ann_start is None:
                    ann_start = start
                    ann_type = _type
                last_end = end
            # Did we end with a remaining annotation?
            if ann_start is not None:
                _add_ann(ann_start, last_end, ann_type)

        return annotations


if __name__ == '__main__':
    # XXX: Hard-coded for testing
    tagger = CoreNLPTagger('stanford-corenlp-2012-04-09')
    print(tagger.tag('Just a test, like the ones they do at IBM.\n'
                     'Or Microsoft for that matter.'))
