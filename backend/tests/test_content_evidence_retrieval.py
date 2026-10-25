import asyncio
from dataclasses import replace
import json

import httpx
import pytest

from movie_companion.content_evidence_retrieval import retrieve_draft_evidence
from movie_companion.evidence_store import EvidenceStore, SourceDocument
from movie_companion.proposal_evidence import verify_origins
from movie_companion.source_sections import SourceSection


def fixture_source():
    parts = [
        ('Plot', 'plot', '\n'.join(f'Lena returns map number {i} to the keeper before dawn.' for i in range(12))),
        ('Filming', 'filming', '\n'.join(f'The crew builds miniature lighthouse number {i} inside a water tank.' for i in range(12))),
        ('Music', 'music', '\n'.join(f'The composer records piano theme number {i} inside a warehouse.' for i in range(12))),
    ]
    text = ''
    sections = []
    for title, category, body in parts:
        start = len(text)
        text += body + '\n'
        sections.append(SourceSection(start, len(text), title, category))
    return SourceDocument('wiki_27205', 27205, text, 'English Wikipedia contributors: Inception',
                          'https://en.wikipedia.org/w/index.php?oldid=123',
                          'enwiki-123-sections-v3-body', sections=tuple(sections))


def transport(requests):
    def handle(request):
        assert request.url.path == '/api/embed'
        body = json.loads(request.content)
        assert body['truncate'] is False
        assert body['model'] == 'nomic-embed-text:v1.5'
        requests.append(body['input'])
        vectors = [[0.0, 1.0] if ('composer' in text or 'music recording' in text)
                   else [1.0, 0.0] for text in body['input']]
        return httpx.Response(200, json={'embeddings': vectors})
    return httpx.MockTransport(handle)


def run(tmp_path, *, source=None, max_batches=2, requests=None):
    requests = [] if requests is None else requests
    async def call():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',
                                    transport=transport(requests)) as client:
            return await retrieve_draft_evidence(client, source=source or fixture_source(),
                                                store=EvidenceStore(tmp_path), max_batches=max_batches)
    return asyncio.run(call())


def test_index_reuse_query_prefix_and_topic_ranking(tmp_path):
    requests = []
    first = run(tmp_path, requests=requests)
    second = run(tmp_path, requests=requests)
    assert first.trace['snapshot_state'] == 'indexed'
    assert second.trace['snapshot_state'] == 'cached'
    assert first.trace['snapshot_key'] == second.trace['snapshot_key']
    assert len(requests) == 3
    assert all(t.startswith('search_document: ') for t in requests[0])
    assert all(t.startswith('search_query: ') for t in requests[1])
    assert len(requests[1]) == 4
    assert second.batches == first.batches
    assert first.batches[0][2].origin.section_category == 'filming'
    assert first.batches[1][2].origin.section_category == 'music'


def test_routing_exact_complete_sentences_and_no_cross_topic_reuse(tmp_path):
    source = fixture_source()
    result = run(tmp_path, max_batches=8)
    seen = set()
    assert len(result.trace['queries']) == 16
    for batch in result.batches:
        assert len(batch) <= 4
        verify_origins(source, batch)
        for passage in batch:
            assert passage.text.endswith('.')
            key = (passage.origin.start, passage.origin.end)
            assert key not in seen
            seen.add(key)
            assert passage.origin.movie_id == 27205
            assert passage.origin.section_category in (
                {'plot'} if passage.purpose == 'story' else {'filming', 'music'})
    for query in result.trace['queries']:
        for selection in query['selected']:
            assert selection['section'] in ({'Plot'} if query['purpose'] == 'story' else {'Filming', 'Music'})


def test_changed_source_revision_is_a_separate_snapshot(tmp_path):
    requests = []
    first = run(tmp_path, requests=requests)
    changed = replace(fixture_source(), revision='enwiki-124-sections-v3-body',
                      source_ref='https://en.wikipedia.org/w/index.php?oldid=124')
    second = run(tmp_path, source=changed, requests=requests)
    assert second.trace['snapshot_state'] == 'indexed'
    assert second.trace['snapshot_key'] != first.trace['snapshot_key']
    assert len(requests) == 4


@pytest.mark.parametrize('max_batches', [0, 9, True])
def test_budget_failures_do_not_call_model(tmp_path, max_batches):
    requests = []
    with pytest.raises(ValueError): run(tmp_path, max_batches=max_batches, requests=requests)
    assert not requests


def test_spoofed_source_fails_before_embedding(tmp_path):
    requests = []
    with pytest.raises(ValueError):
        run(tmp_path, source=replace(fixture_source(), source_ref='https://evil.example/'), requests=requests)
    assert not requests


def test_wrong_movie_in_same_store_does_not_enter_snapshot(tmp_path):
    run(tmp_path)
    changed = replace(fixture_source(), movie_id=329865, source_id='wiki_329865',
                      source_label='English Wikipedia contributors: Arrival (film)')
    result = run(tmp_path, source=changed)
    assert all(p.origin.movie_id == 329865 for b in result.batches for p in b)


def test_invalid_embedding_response_fails_without_drafts(tmp_path):
    async def call():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434', transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={'embeddings': [[0, 0]]}))) as client:
            await retrieve_draft_evidence(client, source=fixture_source(), store=EvidenceStore(tmp_path))
    with pytest.raises(ValueError): asyncio.run(call())


def test_cast_plot_descriptions_and_article_navigation_are_not_fact_evidence(tmp_path):
    from movie_companion.proposal_evidence import evidence_pools
    original = fixture_source()
    tail = ('Main article: Music from the Motion Picture\n'
            'The composer recorded bells underwater for the haunting score.\n'
            'Ada plays Mira, the thief who betrays her brother in the ending.')
    start = len(original.text)
    split = tail.index('Ada plays')
    source = replace(original, text=original.text+tail, sections=original.sections+(
        SourceSection(start,start+split,'Music','music'),
        SourceSection(start+split,start+len(tail),'Cast','casting')))
    pools = evidence_pools(source)
    assert all('Main article:' not in text and 'Ada plays' not in text
               for text, _ in pools['background'])
    assert any('bells underwater' in text for text, _ in pools['background'])
    result = run(tmp_path, source=source, max_batches=8)
    assert all('Ada plays' not in p.text for b in result.batches for p in b)
