import pytest

from movie_companion.evidence_store import SourceDocument
from movie_companion.movie_web_sources import MovieIdentity
from movie_companion.quiz_replacement_completion import NarrativeIntent
from movie_companion.quiz_replacement_evidence import retrieve_replacement_evidence,targeted_story_query
from movie_companion.source_sections import SourceSection
from movie_companion.web_corpus_store import WebCorpusStore


def source(movie_id=1):
    text=('After the flood destroys their home, the family seeks temporary shelter. '
          'They later return to rebuild their lives.\n'
          'The production used a studio water tank for the flood sequence.')
    split=text.index('\n')
    return SourceDocument('story',movie_id,text,'Publisher · Film',
        'https://en.wikipedia.org/w/index.php?oldid=123456789',
        'enwiki-123456789-sections-v3-body','spoiler',(
            SourceSection(0,split+1,'Plot','plot'),
            SourceSection(split+1,len(text),'Production','production')))


def test_movie_sources_validate_and_retrieve_only_complete_plot_sentences(tmp_path):
    store=WebCorpusStore(tmp_path/'corpus.db');store.remember(source(),'web')
    retained=store.movie_sources(1)
    assert len(retained)==1 and retained[0][0]==source() and retained[0][1]=='web'
    evidence,trace=retrieve_replacement_evidence(store,{
        'movie_id':1,'old_question':'Where do they go after the flood?',
        'replacement_brief':'Replace with the consequence of the flood for the family.',
        'evidence':{'explanation':'The flood displaces the family.'}},limit=3)
    assert evidence[0]['excerpt']=='After the flood destroys their home, the family seeks temporary shelter.'
    assert all('studio water tank' not in item['excerpt'] for item in evidence)
    assert trace['movie_sources']==1 and trace['candidate_sentences']==2


def test_retrieval_rejects_invalid_source_listing_requests(tmp_path):
    store=WebCorpusStore(tmp_path/'corpus.db')
    for movie_id,kinds in [(0,('web',)),(1,()),(1,('unknown',))]:
        try:store.movie_sources(movie_id,kinds=kinds)
        except ValueError:pass
        else:raise AssertionError('Invalid source listing must fail')


def intent():
    return NarrativeIntent(question_id='q1',focus='the consequence for the family',
        relation='consequence',required_concepts=[['family'],['shelter','displaced']],
        forbidden_details=[],expected_answer_shape='outcome')


def test_targeted_story_query_uses_identity_and_reviewed_aliases_with_two_revisions():
    movie=MovieIdentity(1,'Flood Film',2024,'Director')
    first=targeted_story_query(movie,intent(),revision=1)
    second=targeted_story_query(movie,intent(),revision=2)
    assert first.startswith('"Flood Film" 2024 film')
    assert 'family' in first and 'shelter' in first and 'plot explanation' in first
    assert 'displaced' in second and 'story analysis' in second and first!=second
    assert len(first)<=500 and len(second)<=500
    with pytest.raises(ValueError,match='revised'):
        targeted_story_query(movie,intent(),revision=3)


def test_contract_terms_are_traced_and_script_plot_sentences_are_eligible(tmp_path):
    store=WebCorpusStore(tmp_path/'contract.db');store.remember(source(),'script')
    target={'movie_id':1,'old_question':'Where do they go?',
        'replacement_brief':'Test the consequence of the flood.',
        'evidence':{'explanation':'The family is displaced.'}}
    evidence,trace=retrieve_replacement_evidence(store,target,intent=intent(),limit=8)
    assert evidence[0]['excerpt'].endswith('.')
    assert evidence[0]['source_kind']=='script'
    assert {'family','shelter'}<=set(trace['query_terms'])
    assert len(evidence)<=8
