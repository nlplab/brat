#!/usr/bin/env python

"""Conversion scripts related to Stanford tools.

Author:     Pontus Stenetorp    <pontus stenetorp se>
Version:    2012-06-26
"""

# TODO: Currently pretty much every single call re-parses the XML, optimise?
# TODO: We could potentially put the lemma into a comment



from collections import defaultdict
from itertools import chain
from os.path import join as path_join
from os.path import dirname
from sys import path as sys_path
from sys import argv, stderr, stdout
from xml.etree import ElementTree

from .ptbesc import unescape as ptb_unescape

try:
    from collections import namedtuple
except ImportError:
    sys_path.append(path_join(dirname(__file__), '..', '..', 'lib'))
    from altnamedtuple import namedtuple

try:
    from annotation import (BinaryRelationAnnotation, EquivAnnotation,
                            TextBoundAnnotation)
except ImportError:
    sys_path.append(path_join(dirname(__file__), '..'))
    from annotation import (BinaryRelationAnnotation, EquivAnnotation,
                            TextBoundAnnotation)

Token = namedtuple('Token', ('word', 'lemma', 'start', 'end', 'pos', 'ner', ))


def _escape_pos_tags(pos):
    pos_res = pos
    for _from, to in (
            ("'", '__SINGLEQUOTE__', ),
            ('"', '__DOUBLEQUOTE__', ),
            ('$', '__DOLLAR__', ),
            (',', '__COMMA__', ),
            ('.', '__DOT__', ),
            (':', '__COLON__', ),
            ('`', '__BACKTICK__', ),
    ):
        pos_res = pos_res.replace(_from, to)
    return pos_res


def _token_by_ids(soup):
    token_by_ids = defaultdict(dict)

    for sent_e in _find_sentences_element(soup).getiterator('sentence'):
        sent_id = int(sent_e.get('id'))
        for tok_e in sent_e.getiterator('token'):
            tok_id = int(tok_e.get('id'))
            tok_word = str(tok_e.find('word').text)
            tok_lemma = str(tok_e.find('lemma').text)
            tok_start = int(tok_e.find('CharacterOffsetBegin').text)
            tok_end = int(tok_e.find('CharacterOffsetEnd').text)
            tok_pos = str(tok_e.find('POS').text)
            tok_ner = str(tok_e.find('NER').text)

            token_by_ids[sent_id][tok_id] = Token(
                word=tok_word,
                lemma=tok_lemma,
                start=tok_start,
                end=tok_end,
                # Escape the PoS since brat dislike $ and .
                pos=_escape_pos_tags(tok_pos),
                ner=tok_ner
            )

    return token_by_ids


def _tok_it(token_by_ids):
    for s_id in sorted(k for k in token_by_ids):
        for t_id in sorted(k for k in token_by_ids[s_id]):
            yield s_id, t_id, token_by_ids[s_id][t_id]


def _soup(xml):
    return ElementTree.fromstring(xml)


def token_offsets(xml):
    soup = _soup(xml)
    token_by_ids = _token_by_ids(soup)
    return [(tok.start, tok.end) for _, _, tok in _tok_it(token_by_ids)]


def sentence_offsets(xml):
    soup = _soup(xml)
    token_by_ids = _token_by_ids(soup)
    sent_min_max = defaultdict(lambda: (2**32, -1, ))
    for s_id, _, tok in _tok_it(token_by_ids):
        s_entry = sent_min_max[s_id]
        sent_min_max[s_id] = (min(tok.start, s_entry[0]),
                              max(tok.end, s_entry[1]), )
    return sorted((s_start, s_end)
                  for s_start, s_end in sent_min_max.values())


def text(xml):
    # It would be nice to have access to the original text, but this actually
    # isn't a part of the XML. Constructing it isn't that easy either, you
    # would have to assume that each "missing" character is a space, but you
    # don't really have any guarantee that this is the case...

    soup = _soup(xml)
    token_by_ids = _token_by_ids(soup)

    # Get the presumed length of the text
    max_offset = -1
    for _, _, tok in _tok_it(token_by_ids):
        max_offset = max(max_offset, tok.end)

    # Then re-construct what we believe the text to be
    text = list(' ' * max_offset)
    for _, _, tok in _tok_it(token_by_ids):
        # Also unescape any PTB escapes in the text while we are at it
        # Note: Since Stanford actually doesn't do all the escapings properly
        # this will sometimes fail! Hint: Try "*/\*".
        unesc_word = ptb_unescape(tok.word)
        text[tok.start:len(unesc_word)] = unesc_word

    return ''.join(text)


def _pos(xml, start_id=1):
    soup = _soup(xml)
    token_by_ids = _token_by_ids(soup)

    curr_id = start_id
    for s_id, t_id, tok in _tok_it(token_by_ids):
        yield s_id, t_id, TextBoundAnnotation(((tok.start, tok.end, ), ),
                                              'T%s' % curr_id, tok.pos, '')
        curr_id += 1


def pos(xml, start_id=1):
    return (a for _, _, a in _pos(xml, start_id=start_id))


def ner(xml, start_id=1):
    soup = _soup(xml)
    token_by_ids = _token_by_ids(soup)

    # Stanford only has Inside and Outside tags, so conversion is easy
    nes = []
    last_ne_tok = None
    prev_tok = None
    for _, _, tok in _tok_it(token_by_ids):
        if tok.ner != 'O':
            if last_ne_tok is None:
                # Start of an NE from nothing
                last_ne_tok = tok
            elif tok.ner != last_ne_tok.ner:
                # Change in NE type
                nes.append(
                    (last_ne_tok.start, prev_tok.end, last_ne_tok.ner, ))
                last_ne_tok = tok
            else:
                # Continuation of the last NE, move along
                pass
        elif last_ne_tok is not None:
            # NE ended
            nes.append((last_ne_tok.start, prev_tok.end, last_ne_tok.ner, ))
            last_ne_tok = None
        prev_tok = tok
    else:
        # Do we need to terminate the last named entity?
        if last_ne_tok is not None:
            nes.append((last_ne_tok.start, prev_tok.end, last_ne_tok.ner, ))

    curr_id = start_id
    for start, end, _type in nes:
        yield TextBoundAnnotation(((start, end), ), 'T%s' % curr_id, _type, '')
        curr_id += 1


def coref(xml, start_id=1):
    soup = _soup(xml)
    token_by_ids = _token_by_ids(soup)

    docs_e = soup.findall('document')
    assert len(docs_e) == 1
    docs_e = docs_e[0]
    # Despite the name, this element contains conferences (note the "s")
    corefs_e = docs_e.findall('coreference')
    if not corefs_e:
        # No coreferences to process
        raise StopIteration
    assert len(corefs_e) == 1
    corefs_e = corefs_e[0]

    curr_id = start_id
    for coref_e in corefs_e:
        if corefs_e.tag != 'coreference':
            # To be on the safe side
            continue

        # This tag is now a full corference chain
        chain = []
        for mention_e in coref_e.getiterator('mention'):
            # Note: There is a "representative" attribute signalling the most
            #   "suitable" mention, we are currently not using this
            # Note: We don't use the head information for each mention
            sentence_id = int(mention_e.find('sentence').text)
            start_tok_id = int(mention_e.find('start').text)
            end_tok_id = int(mention_e.find('end').text) - 1

            mention_id = 'T%s' % (curr_id, )
            chain.append(mention_id)
            curr_id += 1
            yield TextBoundAnnotation(
                ((token_by_ids[sentence_id][start_tok_id].start,
                  token_by_ids[sentence_id][end_tok_id].end), ),
                mention_id, 'Mention', '')

        yield EquivAnnotation('Coreference', chain, '')


def _find_sentences_element(soup):
    # Find the right portion of the XML and do some limited sanity checking
    docs_e = soup.findall('document')
    assert len(docs_e) == 1
    docs_e = docs_e[0]
    sents_e = docs_e.findall('sentences')
    assert len(sents_e) == 1
    sents_e = sents_e[0]

    return sents_e


def _dep(xml, source_element='basic-dependencies'):
    soup = _soup(xml)
    _token_by_ids(soup)

    ann_by_ids = defaultdict(dict)
    for s_id, t_id, ann in _pos(xml):
        ann_by_ids[s_id][t_id] = ann
        yield ann

    curr_rel_id = 1
    for sent_e in _find_sentences_element(soup).getiterator('sentence'):
        sent_id = int(sent_e.get('id'))

        # Attempt to find dependencies as distinctly named elements as they
        #   were stored in the Stanford XML format prior to 2013.
        deps_e = sent_e.findall(source_element)
        if len(deps_e) == 0:
            # Perhaps we are processing output following the newer standard,
            #   check for the same identifier but as a type attribute for
            #   general "dependencies" elements.
            deps_e = list(e for e in sent_e.getiterator('dependencies')
                          if e.attrib['type'] == source_element)
        assert len(deps_e) == 1
        deps_e = deps_e[0]

        for dep_e in deps_e:
            if dep_e.tag != 'dep':
                # To be on the safe side
                continue

            dep_type = dep_e.get('type')
            assert dep_type is not None

            if dep_type == 'root':
                # Skip dependencies to the root node, this behaviour conforms
                #   with how we treated the pre-2013 format.
                continue

            gov_tok_id = int(dep_e.find('governor').get('idx'))
            dep_tok_id = int(dep_e.find('dependent').get('idx'))

            yield BinaryRelationAnnotation(
                'R%s' % curr_rel_id, dep_type,
                'Governor', ann_by_ids[sent_id][gov_tok_id].id,
                'Dependent', ann_by_ids[sent_id][dep_tok_id].id,
                ''
            )
            curr_rel_id += 1


def basic_dep(xml):
    return _dep(xml)


def collapsed_dep(xml):
    return _dep(xml, source_element='collapsed-dependencies')


def collapsed_ccproc_dep(xml):
    return _dep(xml, source_element='collapsed-ccprocessed-dependencies')


if __name__ == '__main__':
    STANFORD_XML = '''<?xml version="1.0" encoding="UTF-8"?>
    <?xml-stylesheet href="CoreNLP-to-HTML.xsl" type="text/xsl"?>
    <root>
      <document>
        <sentences>
          <sentence id="1">
            <tokens>
              <token id="1">
                <word>Stanford</word>
                <lemma>Stanford</lemma>
                <CharacterOffsetBegin>0</CharacterOffsetBegin>
                <CharacterOffsetEnd>8</CharacterOffsetEnd>
                <POS>NNP</POS>
                <NER>ORGANIZATION</NER>
              </token>
              <token id="2">
                <word>University</word>
                <lemma>University</lemma>
                <CharacterOffsetBegin>9</CharacterOffsetBegin>
                <CharacterOffsetEnd>19</CharacterOffsetEnd>
                <POS>NNP</POS>
                <NER>ORGANIZATION</NER>
              </token>
              <token id="3">
                <word>is</word>
                <lemma>be</lemma>
                <CharacterOffsetBegin>20</CharacterOffsetBegin>
                <CharacterOffsetEnd>22</CharacterOffsetEnd>
                <POS>VBZ</POS>
                <NER>O</NER>
              </token>
              <token id="4">
                <word>located</word>
                <lemma>located</lemma>
                <CharacterOffsetBegin>23</CharacterOffsetBegin>
                <CharacterOffsetEnd>30</CharacterOffsetEnd>
                <POS>JJ</POS>
                <NER>O</NER>
              </token>
              <token id="5">
                <word>in</word>
                <lemma>in</lemma>
                <CharacterOffsetBegin>31</CharacterOffsetBegin>
                <CharacterOffsetEnd>33</CharacterOffsetEnd>
                <POS>IN</POS>
                <NER>O</NER>
              </token>
              <token id="6">
                <word>California</word>
                <lemma>California</lemma>
                <CharacterOffsetBegin>34</CharacterOffsetBegin>
                <CharacterOffsetEnd>44</CharacterOffsetEnd>
                <POS>NNP</POS>
                <NER>LOCATION</NER>
              </token>
              <token id="7">
                <word>.</word>
                <lemma>.</lemma>
                <CharacterOffsetBegin>44</CharacterOffsetBegin>
                <CharacterOffsetEnd>45</CharacterOffsetEnd>
                <POS>.</POS>
                <NER>O</NER>
              </token>
            </tokens>
            <parse>(ROOT (S (NP (NNP Stanford) (NNP University)) (VP (VBZ is) (ADJP (JJ located) (PP (IN in) (NP (NNP California))))) (. .))) </parse>
            <basic-dependencies>
              <dep type="nn">
                <governor idx="2">University</governor>
                <dependent idx="1">Stanford</dependent>
              </dep>
              <dep type="nsubj">
                <governor idx="4">located</governor>
                <dependent idx="2">University</dependent>
              </dep>
              <dep type="cop">
                <governor idx="4">located</governor>
                <dependent idx="3">is</dependent>
              </dep>
              <dep type="prep">
                <governor idx="4">located</governor>
                <dependent idx="5">in</dependent>
              </dep>
              <dep type="pobj">
                <governor idx="5">in</governor>
                <dependent idx="6">California</dependent>
              </dep>
            </basic-dependencies>
            <collapsed-dependencies>
              <dep type="nn">
                <governor idx="2">University</governor>
                <dependent idx="1">Stanford</dependent>
              </dep>
              <dep type="nsubj">
                <governor idx="4">located</governor>
                <dependent idx="2">University</dependent>
              </dep>
              <dep type="cop">
                <governor idx="4">located</governor>
                <dependent idx="3">is</dependent>
              </dep>
              <dep type="prep_in">
                <governor idx="4">located</governor>
                <dependent idx="6">California</dependent>
              </dep>
            </collapsed-dependencies>
            <collapsed-ccprocessed-dependencies>
              <dep type="nn">
                <governor idx="2">University</governor>
                <dependent idx="1">Stanford</dependent>
              </dep>
              <dep type="nsubj">
                <governor idx="4">located</governor>
                <dependent idx="2">University</dependent>
              </dep>
              <dep type="cop">
                <governor idx="4">located</governor>
                <dependent idx="3">is</dependent>
              </dep>
              <dep type="prep_in">
                <governor idx="4">located</governor>
                <dependent idx="6">California</dependent>
              </dep>
            </collapsed-ccprocessed-dependencies>
          </sentence>
          <sentence id="2">
            <tokens>
              <token id="1">
                <word>It</word>
                <lemma>it</lemma>
                <CharacterOffsetBegin>46</CharacterOffsetBegin>
                <CharacterOffsetEnd>48</CharacterOffsetEnd>
                <POS>PRP</POS>
                <NER>O</NER>
              </token>
              <token id="2">
                <word>is</word>
                <lemma>be</lemma>
                <CharacterOffsetBegin>49</CharacterOffsetBegin>
                <CharacterOffsetEnd>51</CharacterOffsetEnd>
                <POS>VBZ</POS>
                <NER>O</NER>
              </token>
              <token id="3">
                <word>a</word>
                <lemma>a</lemma>
                <CharacterOffsetBegin>52</CharacterOffsetBegin>
                <CharacterOffsetEnd>53</CharacterOffsetEnd>
                <POS>DT</POS>
                <NER>O</NER>
              </token>
              <token id="4">
                <word>great</word>
                <lemma>great</lemma>
                <CharacterOffsetBegin>54</CharacterOffsetBegin>
                <CharacterOffsetEnd>59</CharacterOffsetEnd>
                <POS>JJ</POS>
                <NER>O</NER>
              </token>
              <token id="5">
                <word>university</word>
                <lemma>university</lemma>
                <CharacterOffsetBegin>60</CharacterOffsetBegin>
                <CharacterOffsetEnd>70</CharacterOffsetEnd>
                <POS>NN</POS>
                <NER>O</NER>
              </token>
              <token id="6">
                <word>.</word>
                <lemma>.</lemma>
                <CharacterOffsetBegin>70</CharacterOffsetBegin>
                <CharacterOffsetEnd>71</CharacterOffsetEnd>
                <POS>.</POS>
                <NER>O</NER>
              </token>
            </tokens>
            <parse>(ROOT (S (NP (PRP It)) (VP (VBZ is) (NP (DT a) (JJ great) (NN university))) (. .))) </parse>
            <basic-dependencies>
              <dep type="nsubj">
                <governor idx="5">university</governor>
                <dependent idx="1">It</dependent>
              </dep>
              <dep type="cop">
                <governor idx="5">university</governor>
                <dependent idx="2">is</dependent>
              </dep>
              <dep type="det">
                <governor idx="5">university</governor>
                <dependent idx="3">a</dependent>
              </dep>
              <dep type="amod">
                <governor idx="5">university</governor>
                <dependent idx="4">great</dependent>
              </dep>
            </basic-dependencies>
            <collapsed-dependencies>
              <dep type="nsubj">
                <governor idx="5">university</governor>
                <dependent idx="1">It</dependent>
              </dep>
              <dep type="cop">
                <governor idx="5">university</governor>
                <dependent idx="2">is</dependent>
              </dep>
              <dep type="det">
                <governor idx="5">university</governor>
                <dependent idx="3">a</dependent>
              </dep>
              <dep type="amod">
                <governor idx="5">university</governor>
                <dependent idx="4">great</dependent>
              </dep>
            </collapsed-dependencies>
            <collapsed-ccprocessed-dependencies>
              <dep type="nsubj">
                <governor idx="5">university</governor>
                <dependent idx="1">It</dependent>
              </dep>
              <dep type="cop">
                <governor idx="5">university</governor>
                <dependent idx="2">is</dependent>
              </dep>
              <dep type="det">
                <governor idx="5">university</governor>
                <dependent idx="3">a</dependent>
              </dep>
              <dep type="amod">
                <governor idx="5">university</governor>
                <dependent idx="4">great</dependent>
              </dep>
            </collapsed-ccprocessed-dependencies>
          </sentence>
        </sentences>
        <coreference>
          <coreference>
            <mention representative="true">
              <sentence>1</sentence>
              <start>1</start>
              <end>3</end>
              <head>2</head>
            </mention>
            <mention>
              <sentence>2</sentence>
              <start>1</start>
              <end>2</end>
              <head>1</head>
            </mention>
            <mention>
              <sentence>2</sentence>
              <start>3</start>
              <end>6</end>
              <head>5</head>
            </mention>
          </coreference>
        </coreference>
      </document>
    </root>
    '''

    def _test_xml(xml_string):
        stdout.write('Text:\n')
        stdout.write(text(xml_string))
        stdout.write('\n')

        stdout.write('\n')
        stdout.write('Part-of-speech:\n')
        for ann in pos(xml_string):
            stdout.write(str(ann))
            stdout.write('\n')

        stdout.write('\n')
        stdout.write('Named Entity Recoginiton:\n')
        for ann in ner(xml_string):
            stdout.write(str(ann))
            stdout.write('\n')

        stdout.write('\n')
        stdout.write('Co-reference:\n')
        for ann in coref(xml_string):
            stdout.write(str(ann))
            stdout.write('\n')

        stdout.write('\n')
        stdout.write('Basic dependencies:\n')
        for ann in basic_dep(xml_string):
            stdout.write(str(ann))
            stdout.write('\n')

        stdout.write('\n')
        stdout.write('Basic dependencies:\n')
        for ann in basic_dep(xml_string):
            stdout.write(str(ann))
            stdout.write('\n')

        stdout.write('\n')
        stdout.write('Collapsed dependencies:\n')
        for ann in collapsed_dep(xml_string):
            stdout.write(str(ann))
            stdout.write('\n')

        stdout.write('\n')
        stdout.write('Collapsed CC-processed dependencies:\n')
        for ann in collapsed_ccproc_dep(xml_string):
            stdout.write(str(ann))
            stdout.write('\n')

        stdout.write('\n')
        stdout.write('Token boundaries:\n')
        stdout.write(str(token_offsets(xml_string)))
        stdout.write('\n')

        stdout.write('\n')
        stdout.write('Sentence boundaries:\n')
        stdout.write(str(sentence_offsets(xml_string)))
        stdout.write('\n')

    if len(argv) < 2:
        xml_strings = (('<string>', STANFORD_XML), )
    else:
        def _xml_gen():
            for xml_path in argv[1:]:
                with open(xml_path, 'r') as xml_file:
                    # We assume UTF-8 here, otherwise ElemenTree will bork
                    yield (xml_path, xml_file.read().decode('utf-8'))
        xml_strings = _xml_gen()

    for xml_source, xml_string in xml_strings:
        try:
            print(xml_source, file=stderr)
            _test_xml(xml_string)
        except BaseException:
            print('Crashed on:', xml_source, file=stderr)
            raise
