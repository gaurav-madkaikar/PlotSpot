"""Scene-scoped script indexing and retrieval, without generation or publication."""
import asyncio
from collections import Counter
from dataclasses import dataclass
import math
import re

import httpx

from .embedding_learning import embed_texts
from .evidence_store import snapshot_key
from .retrieval_learning import rank_passages, retrieve_passages
from .screenplay_source import ScriptSnapshot, script_documents
from .source_sections import section_for_chunk, source_chunks

MODEL = 'nomic-embed-text:v1.5'
MAX_CHARS = 600
OVERLAP = 100
BATCH_SIZE = 32
STOP_WORDS = set('a an the and or of to in on at by for with is are was were be been being it its this that these those he she they his her their them him as from into out up down what which who why how when where does do did can could would should will answer'.split())


def script_lexical_ranks(passages, query):
    """BM25 candidates over narrative dialogue; literal matches are not proof."""
    tokens = lambda text: [t for t in re.findall(r'[a-z0-9]+',text.casefold()) if t not in STOP_WORDS]
    counts = [Counter(tokens(p.text)) for p in passages]
    if not counts:
        return []
    lengths = [sum(c.values()) for c in counts]
    average = sum(lengths)/len(lengths) or 1.
    terms = set(tokens(query))
    frequencies = {t:sum(t in c for c in counts) for t in terms}
    scored = []
    for passage,count,length in zip(passages,counts,lengths):
        score = 0.
        for term in terms:
            tf = count[term]
            if tf:
                idf = math.log(1+(len(counts)-frequencies[term]+.5)/(frequencies[term]+.5))
                score += idf*tf*2.2/(tf+1.2*(.25+.75*length/average))
        if score > 0:
            scored.append((score,passage.passage_id))
    return [pid for _,pid in sorted(scored,key=lambda row:(-row[0],row[1]))]


def _local_client(client):
    if client.base_url != httpx.URL('http://127.0.0.1:11434') or client.follow_redirects:
        raise ValueError('Use local Ollama with redirects disabled')


async def index_script(client, *, snapshot: ScriptSnapshot, store, model=MODEL):
    _local_client(client)
    documents = script_documents(snapshot)
    for document, _ in documents:
        snapshot_key(document, model=model, max_chars=MAX_CHARS, overlap_chars=OVERLAP)
    counts = {'indexed_documents': 0, 'cached_documents': 0, 'chunks': 0}
    for document, _ in documents:
        chunks = source_chunks(document, max_chars=MAX_CHARS, overlap_chars=OVERLAP)
        counts['chunks'] += len(chunks)
        kwargs = dict(source=document, model=model, max_chars=MAX_CHARS, overlap_chars=OVERLAP)
        if await asyncio.to_thread(store.contains_snapshot, **kwargs):
            counts['cached_documents'] += 1
            continue
        vectors = []
        for start in range(0, len(chunks), BATCH_SIZE):
            vectors.extend(await embed_texts(client, model=model,
                           texts=['search_document: ' + c.text for c in chunks[start:start+BATCH_SIZE]]))
        await asyncio.to_thread(store.save_snapshot, chunks=chunks, vectors=vectors, **kwargs)
        counts['indexed_documents'] += 1
    return counts


@dataclass(frozen=True)
class ScriptHit:
    passage_id: str
    score: float
    text: str
    scene: str
    start: int
    end: int
    movie_id: int
    source_ref: str
    revision: str
    released_film_verified: bool = False


async def narrative_alignment(store, *, snapshot, vectors, model=MODEL):
    """Best narrative embedding score per plot unit; not evidence of agreement.

    Fuse these candidate ranks with novelty to avoid prioritizing exclusively
    events missing from an old script version. Review still decides support.
    """
    if not 1 <= len(vectors) <= 200:
        raise ValueError('Bounded plot vectors required')
    passages = []
    for document, _ in script_documents(snapshot):
        loaded = await asyncio.to_thread(store.load_snapshot, source=document, model=model,
                                        max_chars=MAX_CHARS, overlap_chars=OVERLAP)
        passages.extend(p for p in loaded if p.section_title != 'Opening and title material')
    def score():
        return [hits[0].score if (hits := retrieve_passages(v, passages, query_model=model,
                    movie_id=snapshot.movie_id, allow_spoilers=True, k=1)) else 0.
                for v in vectors]
    return await asyncio.to_thread(score)


async def retrieve_script(client, *, snapshot: ScriptSnapshot, store, query: str,
                          allow_spoilers: bool, k: int = 3, model=MODEL, hybrid: bool = False):
    if allow_spoilers is not True:
        raise ValueError('Explicit spoiler consent is required for script retrieval')
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 500:
        raise ValueError('Script query must contain 1 to 500 characters')
    if type(k) is not int or not 1 <= k <= 6:
        raise ValueError('Retrieve 1 to 6 passages')
    if type(hybrid) is not bool:
        raise ValueError('Hybrid retrieval flag must be boolean')
    _local_client(client)
    passages, origins = [], {}
    for document, offset in script_documents(snapshot):
        loaded = await asyncio.to_thread(store.load_snapshot, source=document, model=model,
                                        max_chars=MAX_CHARS, overlap_chars=OVERLAP)
        chunks = source_chunks(document, max_chars=MAX_CHARS, overlap_chars=OVERLAP)
        for passage, chunk in zip(loaded, chunks):
            scene = section_for_chunk(document, chunk)
            origins[passage.passage_id] = (offset+chunk.start, offset+chunk.end, scene.title)
        passages.extend(loaded)
    vector = (await embed_texts(client, model=model, texts=['search_query: ' + query.strip()]))[0]
    ranked = retrieve_passages(vector, passages, query_model=model, movie_id=snapshot.movie_id,
                               allow_spoilers=True, k=k)
    if hybrid:
        narrative = [p for p in passages if p.section_title != 'Opening and title material']
        semantic = rank_passages(vector,narrative,k=len(narrative))
        semantic_rank = {h.passage.passage_id:i for i,h in enumerate(semantic)}
        lexical_rank = {pid:i for i,pid in enumerate(script_lexical_ranks(narrative,query))}
        def fused(hit):
            pid = hit.passage.passage_id
            return 1/(20+semantic_rank[pid]) + (1/(20+lexical_rank[pid]) if pid in lexical_rank else 0.)
        ranked = sorted(semantic,key=lambda h:(-fused(h),h.passage.passage_id))[:k]
    result = []
    for hit in ranked:
        start, end, scene = origins[hit.passage.passage_id]
        if snapshot.text[start:end] != hit.passage.text:
            raise ValueError('Retrieved screenplay span does not match its snapshot')
        result.append(ScriptHit(hit.passage.passage_id, hit.score, hit.passage.text, scene,
                               start, end, snapshot.movie_id, snapshot.source_ref, snapshot.revision))
    return result
