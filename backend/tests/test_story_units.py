from movie_companion.content_proposals import EvidenceOrigin
from movie_companion.story_units import quiz_units, score_ranks


def origin(text, offset=7):
    return EvidenceOrigin(movie_id=27205, source_id='fixture', source_ref='https://en.wikipedia.org/w/index.php?oldid=123',
        revision='fixture', section_title='Plot', section_category='plot', start=offset, end=offset+len(text))


def test_event_units_keep_exact_offsets_and_preceding_pronoun_context():
    text = 'Lena gives Omar the brass key. He unlocks the observatory. The guard closes the outer gate.'
    units = quiz_units([(text, origin(text))])
    assert len(units) == 3
    assert units[1][0] == 'Lena gives Omar the brass key. He unlocks the observatory.'
    assert units[2][0] == 'The guard closes the outer gate.'
    for value, source in units:
        assert text[source.start-7:source.end-7] == value
        assert source.movie_id == 27205 and source.section_category == 'plot'


def test_long_sentences_are_skipped_not_truncated_into_false_claims():
    text = 'Lena ' + 'searches ' * 90 + 'the castle. Omar locks the hidden door.'
    units = quiz_units([(text, origin(text))])
    assert [value for value, _ in units] == ['Omar locks the hidden door.']


def test_tied_similarity_scores_do_not_invent_a_document_order_preference():
    assert score_ranks([.4,.9,.4]) == {1:0,0:1,2:1}
