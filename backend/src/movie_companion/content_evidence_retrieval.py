"""Local, purpose-filtered retrieval for reviewable movie content drafts."""
import asyncio
from dataclasses import dataclass

from .content_proposals import ProposalEvidence
from .embedding_learning import embed_texts
from .evidence_store import snapshot_key
from .ingestion_learning import ingest_source
from .proposal_evidence import evidence_pools, verify_origins
from .retrieval_learning import rank_passages, retrieve_passages
from .source_sections import matches_purpose, source_chunks

VERSION = 'content-topic-retrieval-v2'
MODEL = 'nomic-embed-text:v1.5'
MAX_CHARS = 600
OVERLAP_CHARS = 100
TOPICS = {
    'story': (
        'main character goals and important decisions',
        'relationships conflicts and consequences',
        'turning points revelations and discoveries',
        'ending final events and resolution',
        'obstacles plans and how characters overcome them',
        'important objects locations and their role in the story',
        'story rules causes and effects',
        'character motivations and changes across the story',
    ),
    'background': (
        'unusual practical filming techniques and production challenges',
        'music recording instruments and creative sound design',
        'visual effects miniatures stunts and how scenes were made',
        'casting preparation training and performance techniques',
        'writing inspirations research and script development',
        'filming locations sets and unexpected production events',
        'costumes props and unusual design choices',
        'creative collaboration and technical innovations',
    ),
}


@dataclass(frozen=True)
class RetrievedEvidence:
    batches: list[list[ProposalEvidence]]
    trace: dict


def _select_units(pool, windows, hits, used, *, diversify=False):
    """Rank complete units by their best window covering >= half the unit.

    This is context reconstruction, not semantic entailment. A unit never
    crosses a section or changes its original source offsets.
    """
    scores = {hit.passage.passage_id: hit.score for hit in hits}
    ranked = []
    for text, origin in pool:
        key = (origin.start, origin.end)
        if key in used:
            continue
        supporting = [(scores[pid], pid) for pid, chunk in windows.items()
                      if pid in scores and max(0, min(chunk.end, origin.end)
                                                - max(chunk.start, origin.start)) >= len(text) / 2]
        if supporting:
            score, pid = max(supporting, key=lambda item: (item[0], item[1]))
            ranked.append((score, origin.start, pid, text, origin))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    selected = []
    for entry in ranked:
        if diversify and selected and entry[4].section_title == selected[0][4].section_title:
            continue
        selected.append(entry)
        if len(selected) == 2:
            break
    # Diversity is a preference, not a reason to discard useful remaining units.
    if len(selected) < 2:
        selected.extend(entry for entry in ranked if entry not in selected)
        selected = selected[:2]
    for entry in selected:
        used.add((entry[4].start, entry[4].end))
    return selected


async def retrieve_draft_evidence(client, *, source, store, model=MODEL, max_batches=8):
    if type(max_batches) is not int or not 1 <= max_batches <= 8:
        raise ValueError('Use one to eight retrieval batches')
    if model != MODEL:
        raise ValueError('Content retrieval requires the configured embedding model')
    pools = evidence_pools(source)  # source identity checked before model calls
    if not any(pools.values()):
        raise ValueError('No classified complete passages available')
    settings = dict(model=model, max_chars=MAX_CHARS, overlap_chars=OVERLAP_CHARS)
    state = await ingest_source(client, store=store, source=source, **settings)
    passages = await asyncio.to_thread(store.load_snapshot, source, **settings)
    chunks = source_chunks(source, max_chars=MAX_CHARS, overlap_chars=OVERLAP_CHARS)
    windows = {p.passage_id: c for p, c in zip(passages, chunks)}
    queries = [(purpose, topic) for purpose, topics in TOPICS.items()
               if pools[purpose] for topic in topics[:max_batches]]
    vectors = await embed_texts(client, model=model,
        texts=[f'search_query: {topic}' for _, topic in queries])
    trace = {'version': VERSION, 'embedding_model': model, 'snapshot_state': state,
             'snapshot_key': snapshot_key(source, **settings),
             'max_chars': MAX_CHARS, 'overlap_chars': OVERLAP_CHARS,
             'spoiler_policy': 'internal_drafts_allow_spoilers_not_published',
             'queries': []}
    by_topic = {}
    used = {'story': set(), 'background': set()}
    for (purpose, topic), vector in zip(queries, vectors):
        eligible = [p for p in passages if matches_purpose(p.section_category, purpose)]
        # Validate through the existing boundary, then rank the bounded snapshot
        # in full so later topics can select unused complete sentence groups.
        retrieve_passages(vector, eligible, query_model=model, movie_id=source.movie_id,
                          allow_spoilers=True, k=6)
        hits = rank_passages(vector, eligible, k=len(eligible))
        selected = _select_units(pools[purpose], windows, hits, used[purpose],
                                 diversify=purpose == 'background')
        by_topic[(purpose, topic)] = selected
        trace['queries'].append({'purpose': purpose, 'topic': topic,
            'top_windows': [{'id': h.passage.passage_id, 'score': round(h.score, 6)} for h in hits[:6]],
            'selected': [{'start': e[4].start, 'end': e[4].end, 'window_id': e[2],
                          'score': round(e[0], 6), 'section': e[4].section_title} for e in selected]})
    batches = []
    for index in range(max_batches):
        entries = [(purpose, entry) for purpose, topics in TOPICS.items()
                   for entry in by_topic.get((purpose, topics[index]), [])]
        if not entries:
            continue
        batch = [ProposalEvidence(passage_id=f'P{i+1}', purpose=purpose,
                                  text=entry[3], origin=entry[4])
                 for i, (purpose, entry) in enumerate(entries)]
        verify_origins(source, batch)
        batches.append(batch)
    if not batches:
        raise ValueError('Retrieved windows contain no complete classified passages')
    trace['batch_count'] = len(batches)
    return RetrievedEvidence(batches, trace)
