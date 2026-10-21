import asyncio
import json

import httpx
import pytest

from movie_companion.evidence_store import EvidenceStore
from movie_companion.screenplay_source import (
    SCRIPTS, load_script, parse_script, scene_sections, script_documents,
)
from movie_companion.screenplay_retrieval import index_script, retrieve_script
from movie_companion.source_sections import section_for_chunk, source_chunks
from movie_companion.source_registry import SCRIPT_URLS

STAMP = '2026-10-11T00:00:00+00:00'


def html(movie=27205, suffix=''):
    mapping = SCRIPTS[movie]
    # Synthetic screenplay text, never a copyrighted fixture.
    text = (f'{mapping.header_title}\nWritten by\n{mapping.author}\n{mapping.version_marker}\n'
            'FADE IN:\nThe opening clock rings.\n'
            'INT. CLOCK ROOM - DAY\nKEEPER\nThe red clock holds the secret.\n'
            'EXT. GARDEN - NIGHT\nThe blue garden contains a lantern.\n' + suffix)
    return ('<nav>Unrelated menu</nav><pre>' + text + '</pre><pre>Ignore this second block</pre>').encode()


def snapshot(movie=27205, suffix=''):
    return parse_script(html(movie, suffix), movie_id=movie, retrieved_at=STAMP)


def test_every_screenplay_mapping_has_a_reviewed_exact_url():
    assert {'https://imsdb.com' + mapping.path for mapping in SCRIPTS.values()} == SCRIPT_URLS


@pytest.mark.parametrize('movie', sorted(SCRIPTS))
def test_identity_scenes_and_exact_spans(movie):
    s = snapshot(movie)
    assert not s.eligible_for_quiz
    assert 'Unrelated menu' not in s.text and 'second block' not in s.text
    sections = scene_sections(s.text)
    assert len(sections) == 3
    assert sections[0].title == 'Opening and title material'
    assert 'opening clock' in s.text[sections[0].start:sections[0].end]
    assert ''.join(s.text[p.start:p.end] for p in sections) == s.text
    for document, offset in script_documents(s):
        for chunk in source_chunks(document):
            assert section_for_chunk(document, chunk)
            assert s.text[offset+chunk.start:offset+chunk.end] == chunk.text
        assert document.spoiler_status == 'spoiler'


@pytest.mark.parametrize('mutation', [
    lambda b: b.replace(b'INCEPTION', b'WRONG MOVIE'),
    lambda b: b.replace(b'Christopher Nolan', b'Another writer'),
    lambda b: b.replace(b'SHOOTING SCRIPT', b'NEW VERSION'),
    lambda b: b.replace(b'</pre>', b''),
    lambda b: b.replace(b'INT.', b'ROOM').replace(b'EXT.', b'GARDEN'),
])
def test_changed_or_malformed_sources_fail_closed(mutation):
    with pytest.raises(ValueError):
        parse_script(mutation(html()), movie_id=27205, retrieved_at=STAMP)


def test_encoding_and_hidden_markup():
    body = html().replace(b'red clock', b'<b>caf\xe9 clock</b><script>evil()</script>')
    s = parse_script(body, movie_id=27205, retrieved_at=STAMP)
    assert 'café clock' in s.text and 'evil()' not in s.text
    assert '\r' not in s.text
    with pytest.raises(ValueError):
        parse_script(b'x'*1_000_001, movie_id=27205, retrieved_at=STAMP)
    with pytest.raises(ValueError):
        parse_script(html(), movie_id=True, retrieved_at=STAMP)


def test_reviewed_legacy_double_pre_wrapper_is_supported_but_deeper_nesting_is_not():
    body = html().replace(b'<pre>', b'<pre><pre>', 1).replace(b'</pre>', b'</pre></pre>', 1)
    assert parse_script(body, movie_id=27205, retrieved_at=STAMP).text.startswith('INCEPTION')
    with pytest.raises(ValueError, match='nesting'):
        parse_script(body.replace(b'<pre><pre>', b'<pre><pre><pre>', 1),
                     movie_id=27205, retrieved_at=STAMP)


def test_large_scripts_keep_scenes_and_reject_oversized_scene():
    lines = '\n'.join(f'INT. ROOM {i} - DAY\n' + 'Lantern glows. '*100 for i in range(100))
    s = snapshot(suffix=lines)
    docs = script_documents(s)
    assert len(docs) > 1
    assert ''.join(d.text for d, _ in docs) == s.text
    assert all(len(d.text) <= 80_000 for d, _ in docs)
    with pytest.raises(ValueError, match='scene exceeds'):
        script_documents(snapshot(suffix='x'*81_000))


def test_fetch_cache_refresh_and_tampering(tmp_path):
    requests = []
    def handle(request):
        requests.append(request)
        assert request.url == 'https://imsdb.com/scripts/Inception.html'
        return httpx.Response(200, content=html(suffix='New text.' if len(requests) > 1 else ''),
                              headers={'content-type': 'text/html'})
    async def run():
        async with httpx.AsyncClient(base_url='https://imsdb.com', follow_redirects=False,
                                    transport=httpx.MockTransport(handle)) as client:
            first, status = await load_script(client, movie_id=27205, cache_root=tmp_path)
            assert status == 'fetched'
            second, status = await load_script(client, movie_id=27205, cache_root=tmp_path)
            assert status == 'cached' and first == second and len(requests) == 1
            third, status = await load_script(client, movie_id=27205, cache_root=tmp_path, refresh=True)
            assert third.revision != first.revision and status == 'fetched'
            path = tmp_path/'27205.json'
            record = json.loads(path.read_text()); record['text'] += '\nTampered'
            path.write_text(json.dumps(record))
            with pytest.raises(ValueError, match='fingerprint'):
                await load_script(client, movie_id=27205, cache_root=tmp_path)
    asyncio.run(run())


@pytest.mark.parametrize('status, headers, body', [
    (302, {'location': 'https://evil.test'}, b''),
    (200, {'content-type': 'application/json'}, b'{}'),
    (200, {'content-type': 'text/html'}, b'x'*1_000_001),
])
def test_bad_network_response_never_cached(tmp_path, status, headers, body):
    async def run():
        async with httpx.AsyncClient(base_url='https://imsdb.com', follow_redirects=False,
                transport=httpx.MockTransport(lambda r: httpx.Response(status, headers=headers, content=body))) as client:
            with pytest.raises((ValueError, httpx.HTTPStatusError)):
                await load_script(client, movie_id=27205, cache_root=tmp_path)
    asyncio.run(run())
    assert not list(tmp_path.glob('*.json'))


def test_index_reuse_retrieval_consent_and_revision(tmp_path):
    requests = []
    def handle(request):
        data = json.loads(request.content)
        assert request.url.path == '/api/embed'
        assert data['truncate'] is False and len(data['input']) <= 32
        requests.append(data['input'])
        vectors = [[1.0, 0.0] if ('red clock' in t or t.startswith('search_query:')) else [0.0, 1.0]
                   for t in data['input']]
        return httpx.Response(200, json={'embeddings': vectors})
    async def run():
        store = EvidenceStore(tmp_path)
        s = snapshot()
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434', transport=httpx.MockTransport(handle)) as client:
            first = await index_script(client, snapshot=s, store=store)
            count = len(requests)
            second = await index_script(client, snapshot=s, store=store)
            assert first['indexed_documents'] == second['cached_documents'] == 1
            assert len(requests) == count
            for consent in (False, 1, 'true'):
                with pytest.raises(ValueError, match='consent'):
                    await retrieve_script(client, snapshot=s, store=store, query='red clock', allow_spoilers=consent)
            assert len(requests) == count
            await index_script(client, snapshot=snapshot(603), store=store)
            hits = await retrieve_script(client, snapshot=s, store=store, query='red clock', allow_spoilers=True)
            assert hits[0].scene == 'INT. CLOCK ROOM - DAY'
            assert all(h.movie_id == 27205 and h.revision == s.revision for h in hits)
            assert all(h.text == s.text[h.start:h.end] and not h.released_film_verified for h in hits)
            with pytest.raises(ValueError, match='missing or incomplete'):
                await retrieve_script(client, snapshot=snapshot(suffix='New revision.'), store=store,
                                      query='clock', allow_spoilers=True)
    asyncio.run(run())


def test_nonlocal_or_redirecting_clients_fail_before_calls(tmp_path):
    calls = []
    async def run():
        store = EvidenceStore(tmp_path)
        for base, redirects in [('https://remote.test', False), ('http://127.0.0.1:11434', True)]:
            async with httpx.AsyncClient(base_url=base, follow_redirects=redirects,
                    transport=httpx.MockTransport(lambda r: calls.append(r))) as client:
                with pytest.raises(ValueError, match='local Ollama'):
                    await index_script(client, snapshot=snapshot(), store=store)
                with pytest.raises(ValueError, match='local Ollama'):
                    await retrieve_script(client, snapshot=snapshot(), store=store,
                                          query='clock', allow_spoilers=True)
    asyncio.run(run())
    assert calls == []


def test_interrupted_embedding_does_not_save_partial_document(tmp_path):
    calls = []
    s = snapshot(suffix='\n'.join(f'INT. ROOM {i} - DAY\nA lantern glows.' for i in range(70)))
    def handle(request):
        calls.append(request)
        inputs = json.loads(request.content)['input']
        if len(calls) == 2:
            return httpx.Response(503)
        return httpx.Response(200, json={'embeddings': [[1.0, 0.0] for _ in inputs]})
    async def run():
        store = EvidenceStore(tmp_path)
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434', transport=httpx.MockTransport(handle)) as client:
            with pytest.raises(httpx.HTTPStatusError):
                await index_script(client, snapshot=s, store=store)
        for document, _ in script_documents(s):
            assert not store.contains_snapshot(document, model='nomic-embed-text:v1.5', max_chars=600, overlap_chars=100)
    asyncio.run(run())


def test_hybrid_scene_retrieval_recovers_literal_detail_missed_by_embeddings(tmp_path):
    def handle(request):
        texts = json.loads(request.content)['input']
        return httpx.Response(200,json={'embeddings':[
            [1.,0.] if t.startswith('search_query:') or 'red clock' in t else [0.,1.] for t in texts]})
    async def run():
        store = EvidenceStore(tmp_path)
        script = snapshot()
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',transport=httpx.MockTransport(handle)) as client:
            await index_script(client,snapshot=script,store=store)
            args = dict(snapshot=script,store=store,query='blue garden lantern',allow_spoilers=True,k=1)
            semantic = await retrieve_script(client,**args)
            hybrid = await retrieve_script(client,**args,hybrid=True)
            assert semantic[0].scene == 'INT. CLOCK ROOM - DAY'
            assert hybrid[0].scene == 'EXT. GARDEN - NIGHT'
            assert hybrid[0].text == script.text[hybrid[0].start:hybrid[0].end]
            assert not hybrid[0].released_film_verified
    asyncio.run(run())
