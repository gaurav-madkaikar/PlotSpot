"""Retrieval behavior/isolation fixtures, not evidence of model accuracy."""
from dataclasses import replace

import pytest

from movie_companion.discussion_retrieval import question_scope, retrieve_discussion_passages
from movie_companion.retrieval_learning import EmbeddedPassage

MODEL = 'fixture-model'


def passage(identifier, text, vector, *, category='plot', title='Plot', movie_id=155, spoiler='safe'):
    return EmbeddedPassage(identifier, movie_id, text, vector, MODEL, 'Authored fixture', spoiler, title, category)


def retrieve(question, passages, **kwargs):
    return retrieve_discussion_passages(question=question, query_vector=[1., 0.], passages=passages,
                                       movie_id=155, query_model=MODEL, **kwargs)


@pytest.mark.parametrize('question,scope', [
    ('Why does the detective claim to be the thief?', 'story'),
    ('What happens at the end?', 'story'),
    ('Who escapes the warehouse?', 'story'),
    ('How does the character betray her partner?', 'story'),
    ('Who directed the film?', 'all'),
    ('How was the ferry scene filmed?', 'all'),
    ('Who composed the music?', 'all'),
    ('What does the ending symbolize?', 'all'),
    ('What themes does the story explore?', 'all'),
    ('What do you think of the ending?', 'all'),
    ('Why does the hero escape, and how was the stunt filmed?', 'all'),
    ('Tell me about the movie.', 'all'),
])
def test_conservative_scope_keeps_mixed_and_interpretive_questions_broad(question, scope):
    assert question_scope(question) == scope


def test_specific_event_cannot_be_crowded_out_by_high_similarity_themes():
    event = passage('event', 'The detective claims to be the thief to lure the rival into a trap.', [0.4, 0.9])
    themes = [passage(f'theme-{i}', 'The detective represents moral authority and the thief symbolizes fear.',
                      [1., .01*i], category='other', title='Themes') for i in range(6)]
    assert retrieve('Why does the detective claim to be the thief?', [*themes, event])[0].passage is event


def test_lexical_anchor_survives_dense_topic_similarity_in_broad_question():
    rare = passage('rare', 'The production used a mechanical zeotrope for the effect.', [.1, 1.], category='effects', title='Effects')
    others = [passage(f'dense-{i}', 'The production used a camera for the effect.', [1., .01*i], category='effects', title='Effects') for i in range(8)]
    assert rare in [h.passage for h in retrieve('What zeotrope did production use?', [*others, rare])]


def test_no_word_overlap_retains_vector_fallback_and_cosine_score():
    a = passage('a', 'A knight rides home.', [1., 0.])
    b = passage('b', 'A tree grows.', [0., 1.])
    hits = retrieve('xyzzy', [b, a])
    assert [h.passage for h in hits] == [a, b]
    assert hits[0].score == pytest.approx(1.)


def test_classified_article_without_plot_abstains_for_event_question():
    music = passage('music', 'The crew discusses the ending music.', [1., 0.], category='music', title='Music')
    assert retrieve('What happens at the ending?', [music]) == []


def test_unclassified_learning_fixture_keeps_existing_retrieval_contract():
    item = passage('fixture', 'The detective escapes the warehouse.', [1., 0.], category='other', title='Unclassified')
    assert retrieve('Who escapes the warehouse?', [item])[0].passage is item


def test_scope_and_spoiler_filter_precede_words_and_ranks():
    safe = passage('safe', 'A vague story about a detective.', [0., 1.])
    other = passage('other', 'The detective claims to be a thief.', [1., 0.], movie_id=202)
    ending = passage('ending', 'The detective claims to be a thief.', [1., 0.], spoiler='unknown')
    hits = retrieve('Who claims to be a thief?', [other, ending, safe], allow_spoilers=False)
    assert [h.passage for h in hits] == [safe]


@pytest.mark.parametrize('bad', [
    {'vector': [1.]}, {'vector': [0., 0.]}, {'vector': [float('nan'), 1.]},
    {'embedding_model': 'wrong-model'},
])
def test_invalid_eligible_vectors_cannot_be_hidden_by_section_routing(bad):
    item = replace(passage('bad', 'Theme commentary.', [1., 0.], category='other', title='Themes'), **bad)
    with pytest.raises(ValueError): retrieve('What happens at the ending?', [item])


def test_deterministic_ties_and_inputs_are_preserved():
    inputs = [passage('b', 'A courier escapes.', [1., 0.]), passage('a', 'A courier escapes.', [1., 0.])]
    before = list(inputs)
    assert [h.passage.passage_id for h in retrieve('Who escapes?', inputs)] == ['a', 'b']
    assert inputs == before


@pytest.mark.parametrize('k', [0, 7, True])
def test_k_is_bounded(k):
    with pytest.raises(ValueError): retrieve('A question', [], k=k)


@pytest.mark.parametrize('question', ['', ' ', 'x'*1001, None])
def test_invalid_question_rejected_before_ranking(question):
    with pytest.raises(ValueError): retrieve(question, [])
