from dataclasses import replace
import pytest

from movie_companion.chunking_learning import chunk_text
from movie_companion.passage_location import PassageLocation
from movie_companion.retrieval_learning import EmbeddedPassage, RetrievalHit
from movie_companion.discussion_context import build_discussion_context, validate_support_option, SupportOption

KEY = 'a' * 64
TEXT = 'A harmless introductory sentence. The makeup artist instructed the actor to scrunch his face so cracks appeared as he relaxed. A final unrelated detail.'


def passages(text=TEXT):
    return [EmbeddedPassage(KEY[:32]+f'_{i:03}', 155, c.text, [1., 0.], 'fixture', 'Fixture', 'safe', 'Effects', 'effects',
        PassageLocation(KEY, 155, 'Fixture', 'safe', text, c.start, c.end, 0, len(text), 'Effects', 'effects'))
        for i,c in enumerate(chunk_text(text, max_chars=80, overlap_chars=20))]


def context(pool, anchors=None, allow=False):
    anchors = pool[:1] if anchors is None else anchors
    return build_discussion_context([RetrievalHit(p, .9) for p in anchors], pool,
        movie_id=155, allow_spoilers=allow, query_vector=[1.,0.])


def test_recovers_complete_cross_window_sentence_with_original_citation_ids():
    pool=passages(); hits,opts=context(pool, [pool[1]])
    option=next(o for o in opts if 'scrunch' in o.text)
    assert option.text == TEXT[34:126]
    assert len(option.citation_ids)==2
    assert len(hits)<=6
    assert all(h.passage in pool for h in hits)
    validate_support_option(option,hits)
    assert pool[1].text == TEXT[60:140]


@pytest.mark.parametrize('change', ['movie','source','spoiler','bounds','text'])
def test_tampered_location_rejected(change):
    pool=passages();loc=pool[0].location
    values={'movie':{'movie_id':999},'source':{'source_key':'b'*64},'spoiler':{'spoiler_status':'unknown'},
            'bounds':{'start':True},'text':{'text':'changed'+TEXT}}[change]
    pool[0]=replace(pool[0],location=replace(loc,**values))
    with pytest.raises(ValueError):context(pool)


def test_missing_or_spoiler_window_cannot_complete_sentence():
    pool=passages()
    _,opts=context(pool[:1])
    assert not any('scrunch' in o.text for o in opts)
    unsafe=replace(pool[1],spoiler_status='spoiler',location=replace(pool[1].location,spoiler_status='spoiler'))
    _,opts=context([pool[0],unsafe])
    assert not any('scrunch' in o.text for o in opts)


def test_another_revision_cannot_fill_a_gap():
    pool=passages(); other=replace(pool[1],passage_id='b'*32+'_001',location=replace(pool[1].location,source_key='b'*64))
    _,opts=context([pool[0],other])
    assert not any('scrunch' in o.text for o in opts)


def test_no_locations_use_complete_fixture_sentences_without_guessing_neighbors():
    p=EmbeddedPassage('fixture',155,'A complete useful fixture sentence. An unfinished fragment',[1.,0.],'fixture','Fixture','safe')
    hits,opts=context([p])
    assert opts == [SupportOption('A complete useful fixture sentence.',('fixture',))]
    assert len(hits)==1


def test_a_sentence_crossing_section_boundary_is_not_completed():
    pool=passages();split=80
    pool[0]=replace(pool[0],location=replace(pool[0].location,section_end=split))
    pool[1]=replace(pool[1],section_title='Other',location=replace(pool[1].location,section_start=60,section_title='Other'))
    _,opts=context(pool[:2])
    assert not any('scrunch' in o.text for o in opts)


def test_fake_anchor_with_a_real_id_is_rejected():
    pool=passages()
    with pytest.raises(ValueError,match='differs'):
        context(pool,[replace(pool[0],text='Invented source text')])


def test_cross_window_quote_maps_to_both_original_ids():
    import json
    from movie_companion.grounding_learning import _parse_supported_answer
    pool=passages();hits,options=context(pool,[pool[1]])
    option=next(o for o in options if 'scrunch' in o.text)
    answer=_parse_supported_answer(json.dumps({'status':'answered','answer':'He scrunched his face.',
        'evidence_quotes':[option.text]}),hits,offered_options=options)
    assert answer.citation_ids==option.citation_ids


def test_oversize_sentences_are_not_truncated_into_evidence():
    pool=passages('The crew ' + 'worked ' * 100 + 'carefully.')
    _,opts=context(pool)
    assert opts == []


@pytest.mark.parametrize('option', [SupportOption('Invented source evidence not present here.',(KEY[:32]+'_000',)),
                                    SupportOption(TEXT[34:125],(KEY[:32]+'_000',)),
                                    SupportOption(TEXT[34:125],('unknown',))])
def test_invented_or_incompletely_attributed_options_fail(option):
    with pytest.raises(ValueError):validate_support_option(option,[RetrievalHit(p,.9) for p in passages()])


def identity_context(text, question='What does Mira learn about her visions?'):
    pool=passages(text)
    anchor=next(p for p in pool if 'Cole realizes' in p.text)
    return build_discussion_context([RetrievalHit(anchor,.9)],pool,movie_id=155,
        allow_spoilers=False,query_vector=[1.,0.],question=question)


def test_context_recovers_name_sentence_and_uses_original_ids():
    text='Linguist Mira Cole joins the expedition. '+('The visitors wait patiently. '*6)+'Cole realizes her visions show future events.'
    hits,options=identity_context(text)
    names=[o for o in options if o.identity_context]
    assert len(names)==1
    assert names[0].text=='Linguist Mira Cole joins the expedition.'
    assert names[0].citation_ids==(KEY[:32]+'_000',)
    validate_support_option(names[0],hits)
    assert len(hits)<=6


def test_ambiguous_name_pairs_do_not_authorize_an_identity():
    text='Mira Cole joins the expedition. Cole Mira waits by the ship. '+('The visitors wait patiently. '*6)+'Cole realizes her visions show future events.'
    _,options=identity_context(text)
    assert not any(o.identity_context for o in options)


def test_unstated_name_cannot_be_inferred_from_surname():
    text='A linguist joins the expedition. '+('The visitors wait patiently. '*6)+'Cole realizes her visions show future events.'
    _,options=identity_context(text)
    assert not any(o.identity_context for o in options)


def test_name_context_cannot_use_spoiler_ineligible_windows():
    text='Linguist Mira Cole joins the expedition. '+('The visitors wait patiently. '*6)+'Cole realizes her visions show future events.'
    pool=passages(text);first=pool[0]
    pool[0]=replace(first,spoiler_status='unknown',location=replace(first.location,spoiler_status='unknown'))
    anchor=next(p for p in pool if 'Cole realizes' in p.text)
    _,options=build_discussion_context([RetrievalHit(anchor,.9)],pool,movie_id=155,
        allow_spoilers=False,query_vector=[1.,0.],question='What does Mira learn?')
    assert not any(o.identity_context for o in options)
