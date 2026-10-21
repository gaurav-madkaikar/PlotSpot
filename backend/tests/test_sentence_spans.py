import pytest

from movie_companion.sentence_spans import complete_sentence_spans


def sentences(text):
    spans = complete_sentence_spans(text)
    assert all(0 <= start < end <= len(text) for start, end in spans)
    assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:]))
    return [text[start:end] for start, end in spans]


@pytest.mark.parametrize('text', [
    'Screenwriters Cindy Davis Hewitt and Donald H. Hewitt wrote dialogue to match existing lip movements.',
    'Dr. Liet Kynes inspired the costume design for the film.',
    'J. R. Smith measured a 2.5 metre miniature for the shot.',
    'The U.S. crew used 35 mm film for the scene.',
    'The crew used props from Acme Inc. Studios on the set.',
    'The cinematographer’s lighting rig used soft illumination rather than harsh lamps.',
])
def test_names_abbreviations_and_numbers_stay_in_one_exact_sentence(text):
    assert sentences(text) == [text]


def test_headings_blank_lines_references_and_trailing_fragment():
    text = 'Production\n\n  The crew built a practical set.[12][13] Next they lit it carefully.\nAn unfinished final thought'
    assert sentences(text) == ['The crew built a practical set.', 'Next they lit it carefully.']


def test_quoted_terminal_punctuation_preserves_original_bytes():
    text = '  The director said, “We built it ourselves.” Then the crew filmed it!  '
    assert sentences(text) == ['The director said, “We built it ourselves.”', 'Then the crew filmed it!']


@pytest.mark.parametrize('text', ['Production heading', 'The advisor was Dr.', 'Their writer was Donald H.',
                                  'An unfinished remark...', ''])
def test_unfinished_or_ambiguous_endings_abstain(text):
    assert sentences(text) == []


def test_known_ending_does_not_discard_sentence_after_decimal():
    text = 'The model measured 1.5 metres. Its surface was hand-painted.'
    assert sentences(text) == ['The model measured 1.5 metres.', 'Its surface was hand-painted.']


def test_lettered_footnote_keeps_the_following_sentence_boundary():
    text='Most actors joined the film in 2018.[a] Johnson named characters after musicians he enjoyed.[30]'
    assert sentences(text)==['Most actors joined the film in 2018.',
                             'Johnson named characters after musicians he enjoyed.']
