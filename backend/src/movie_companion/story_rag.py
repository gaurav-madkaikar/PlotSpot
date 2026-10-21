"""Script-assisted live story flows, gated by a measured frozen-policy evaluation."""
import asyncio
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
import hashlib
import json
import re
import httpx
from pathlib import Path
from time import monotonic
from uuid import uuid4

from .content_evidence_retrieval import TOPICS, _select_units
from .embedding_learning import embed_texts
from .evidence_store import EvidenceStore
from .local_models import DIGESTS, verify_local_model
from .movie_questions import MovieAnswer, QuestionCitation, ScriptContext
from .movie_quiz import QuizItem
from .preparation_jobs import atomic_json
from .proposal_evidence import evidence_pools
from .retrieval_learning import rank_passages, retrieve_passages
from .screenplay_retrieval import MODEL as EMBEDDING_MODEL, index_script, narrative_alignment, retrieve_script
from .screenplay_source import SCRIPTS, load_script, scene_sections
from .source_sections import source_chunks
from .story_verification import MODEL, POLICY, StoryDrafts, StoryEvidence, draft_from_seed, normalized, propose_quiz_seed, propose_story, review_quiz_seeds, review_story, select_script_context
from .story_units import quiz_units, score_ranks
from .vector_math import cosine_similarity

BACKEND = Path(__file__).resolve().parents[2]


def policy_fingerprint():
    root = Path(__file__).parent
    files = ('story_verification.py', 'quiz_narrative_quality.py', 'story_rag.py',
             'untrusted_evidence.py',
             'story_units.py', 'screenplay_source.py', 'screenplay_retrieval.py',
             'movie_questions.py', 'quiz_generation.py')
    return hashlib.sha256(json.dumps({name: hashlib.sha256((root/name).read_bytes()).hexdigest()
                                     for name in files}, sort_keys=True).encode()).hexdigest()


LOADED_IMPLEMENTATION = policy_fingerprint()


@dataclass
class StoryContext:
    evidence: list[StoryEvidence]
    citations: dict
    script: ScriptContext
    trace: dict


class StoryRag:
    def __init__(self, script_client, *, cache_root=None, evidence_path=None, gate_path=None, trace_root=None):
        self.script_client = script_client
        self.cache_root = cache_root or BACKEND/'data/private/screenplays'
        self.evidence_path = evidence_path or BACKEND/'data/content-evidence'
        self.gate_path = gate_path or BACKEND/'data/private/story-rag-gate.json'
        self.trace_root = trace_root or BACKEND/'data/private/story-rag-traces'
        self.store = None

    @staticmethod
    def handles(question):
        # Production/metadata questions continue using the full article path.
        return not re.search(r'\b(direct(?:or|ed|ing)?|compos(?:er|ed)?|score|soundtrack|filmed|filming|production|budget|revenue|cast|actor|actress|release|award|cinematograph\w*)\b', question.casefold())

    def _evaluated_gate(self, movie_id):
        if movie_id not in SCRIPTS:
            return None
        try:
            if self.gate_path.stat().st_size > 10000:
                return None
            gate = json.loads(self.gate_path.read_text())
            valid = (gate.get('passed') is True and gate.get('policy') == POLICY
                    and gate.get('implementation_sha256') == LOADED_IMPLEMENTATION
                    and policy_fingerprint() == LOADED_IMPLEMENTATION
                    and gate.get('model_digest') == DIGESTS[MODEL])
            return gate if valid else None
        except (OSError, ValueError, TypeError, AttributeError):
            return None

    def enabled(self, movie_id):
        return self._evaluated_gate(movie_id) is not None

    def quiz_enabled(self, movie_id):
        gate = self._evaluated_gate(movie_id)
        movies = gate.get('quiz_movies',[]) if gate is not None else []
        return (isinstance(movies,list) and len(movies)<=3 and all(type(i) is int for i in movies)
                and movie_id in movies)

    async def context(self, client, *, source, passages, query, script_query=None, existing_questions=None, excluded_origins=()):
        # Validate Wikipedia identity and exact passage snapshot before model I/O.
        pools = evidence_pools(source)
        expected = source_chunks(source, max_chars=600, overlap_chars=100)
        if len(passages) != len(expected) or any(p.text != c.text or p.movie_id != source.movie_id
                                                for p, c in zip(passages, expected)):
            raise ValueError('Released-film passage snapshot mismatch')
        plot = [p for p in passages if p.section_category == 'plot']
        if not plot or not pools['story']:
            return None
        await verify_local_model(client, MODEL)
        await verify_local_model(client, EMBEDDING_MODEL)
        snapshot, cache_state = await load_script(self.script_client, movie_id=source.movie_id, cache_root=self.cache_root)
        if self.store is None:
            self.store = await asyncio.to_thread(EvidenceStore, self.evidence_path)
        indexed = await index_script(client, snapshot=snapshot, store=self.store)
        if existing_questions is not None:
            pool = quiz_units(pools['story'])
            pool = [(text, origin) for text, origin in pool
                    if not any(origin.start < end and start < origin.end for start, end in excluded_origins)]
            if not pool:
                return None
            if len(existing_questions) > 40 or len(pool) > 200:
                raise ValueError('Story coverage comparison exceeds budget')
            texts = ['search_query: '+q for q in existing_questions] + ['search_document: '+t for t,_ in pool]
            vectors = []
            for offset in range(0,len(texts),32):
                vectors.extend(await embed_texts(client,model=EMBEDDING_MODEL,texts=texts[offset:offset+32]))
            known = vectors[:len(existing_questions)]
            coverage = []
            for (text, origin), vector in zip(pool,vectors[len(existing_questions):]):
                similarity = max((cosine_similarity(vector,q) for q in known), default=0.)
                coverage.append((1-similarity,origin.start,'coverage',text,origin))
            # Novelty alone prioritizes details that may be absent from older
            # screenplays. Fuse candidate ranks, without treating similarity as
            # agreement or a substitute for either semantic review.
            alignment = await narrative_alignment(self.store, snapshot=snapshot,
                                                   vectors=vectors[len(existing_questions):])
            novelty_rank = score_ranks([row[0] for row in coverage])
            alignment_rank = score_ranks(alignment)
            ranked = [coverage[i] for i in sorted(range(len(coverage)),key=lambda i:
                (-(1/(20+novelty_rank[i])+1/(20+alignment_rank[i])),coverage[i][1]))]
            selected = []
            while ranked and len(selected) < 3:
                best = ranked[0]
                selected.append(best)
                # Contextual units can overlap; retain one occurrence of an event.
                ranked = [row for row in ranked if not (row[4].start < best[4].end and best[4].start < row[4].end)]
            strategy = 'least_covered_plot_sentences'
        else:
            vector = (await embed_texts(client, model=EMBEDDING_MODEL, texts=['search_query: '+query]))[0]
            retrieve_passages(vector, plot, query_model=EMBEDDING_MODEL, movie_id=source.movie_id,
                              allow_spoilers=True, k=3)
            hits = rank_passages(vector, plot, k=len(plot))
            windows = {p.passage_id: c for p, c in zip(passages, expected)}
            selected = _select_units(pools['story'], windows, hits, set())
            strategy = 'question_relevance'
        if not selected:
            return None
        evidence, citations, wiki_trace = [], {}, []
        for index, (score, _, _, text, origin) in enumerate(selected):
            alias = f'W{index+1}'
            evidence.append(StoryEvidence(alias=alias, text=text))
            citations[alias] = QuestionCitation(passage_id=hashlib.sha256(f'{source.revision}:{origin.start}:{origin.end}'.encode()).hexdigest()[:32], source_label=source.source_label,
                    source_ref=source.source_ref, revision=source.revision, excerpt=text)
            wiki_trace.append({'alias': alias, 'score': score, 'origin': origin.model_dump()})
        if existing_questions is not None:
            return StoryContext(evidence, citations,
                ScriptContext(source_ref=snapshot.source_ref, version=SCRIPTS[source.movie_id].version_label),
                {'policy': POLICY, 'implementation_sha256': LOADED_IMPLEMENTATION,
                 'model': MODEL, 'model_digest': DIGESTS[MODEL],
                 'embedding_model': EMBEDDING_MODEL, 'embedding_digest': DIGESTS[EMBEDDING_MODEL],
                 'movie_id': source.movie_id, 'evidence_strategy': strategy,
                 'wiki_revision': source.revision, 'script_revision': snapshot.revision,
                 'source_cache': cache_state, 'index': indexed, 'wiki_hits': wiki_trace, 'script_hits': []})
        script_hits = []
        # Retrieve scene context for each selected released-film passage, not just
        # the vague topic. Scripts still need agreement checks after retrieval.
        for item in evidence:
            retrieved = await retrieve_script(client, snapshot=snapshot, store=self.store,
                                               query=(script_query or item.text)[:500], allow_spoilers=True, k=6)
            added = 0
            for hit in retrieved:
                if len(hit.text) < 20:
                    continue
                if hit.scene == 'Opening and title material':
                    continue  # Header/title words must not count as narrative evidence.
                if any(hit.start < other.end and other.start < hit.end for other in script_hits):
                    continue
                script_hits.append(hit)
                added += 1
                if len(script_hits) >= 3 or added >= 2:
                    break
            if len(script_hits) >= 3:
                break
        if not script_hits:
            return None
        script_evidence, script_trace = self.script_evidence(snapshot, script_hits)
        if not script_evidence:
            return None
        evidence.extend(script_evidence)
        return StoryContext(evidence, citations,
              ScriptContext(source_ref=snapshot.source_ref, version=SCRIPTS[source.movie_id].version_label),
              {'policy': POLICY, 'implementation_sha256': LOADED_IMPLEMENTATION,
               'model':MODEL, 'model_digest':DIGESTS[MODEL],
               'embedding_model':EMBEDDING_MODEL, 'embedding_digest':DIGESTS[EMBEDDING_MODEL],
               'movie_id': source.movie_id, 'evidence_strategy':strategy, 'wiki_revision': source.revision,
               'script_revision': snapshot.revision, 'source_cache': cache_state,
               'index': indexed, 'wiki_hits': wiki_trace, 'script_hits': script_trace})

    @staticmethod
    def script_evidence(snapshot, script_hits):
        evidence, script_trace = [], []
        scenes = scene_sections(snapshot.text)
        for hit in script_hits:
            if (not 0 <= hit.start < hit.end <= len(snapshot.text)
                    or hit.movie_id != snapshot.movie_id or hit.revision != snapshot.revision
                    or hit.source_ref != snapshot.source_ref
                    or snapshot.text[hit.start:hit.end] != hit.text):
                raise ValueError('Script hit provenance mismatch')
            # Parent context recovers dialogue around a small embedding window.
            scene = next(s for s in scenes if s.start <= hit.start < hit.end <= s.end)
            if scene.title == 'Opening and title material':
                continue
            start, end = max(scene.start, hit.start-300), min(scene.end, hit.end+300)
            if start > scene.start:
                newline = snapshot.text.find('\n', start, hit.start)
                if newline >= 0:
                    start = newline+1
            if end < scene.end:
                newline = snapshot.text.rfind('\n', hit.end, end)
                if newline >= 0:
                    end = newline
            text = snapshot.text[start:end]
            if len(text) < 20 or len(text) > 1200:
                continue
            if any(start < record['end'] and record['start'] < end for record in script_trace):
                continue
            alias = f'S{len(evidence)+1}'
            evidence.append(StoryEvidence(alias=alias, text=text))
            script_trace.append({'alias': alias, **{k: v for k, v in asdict(hit).items() if k != 'text'},
                                 'start':start, 'end':end, 'vector_start':hit.start, 'vector_end':hit.end})
            if len(evidence) == 3:
                break
        return evidence, script_trace

    async def focus_quiz_context(self, client, context, draft):
        """Retrieve the proposed relation, instead of an entire plot paragraph."""
        movie_id = context.trace['movie_id']
        released = next(e for e in context.evidence if e.alias == draft.wiki_alias)
        snapshot, _ = await load_script(self.script_client, movie_id=movie_id, cache_root=self.cache_root)
        if snapshot.revision != context.trace['script_revision']:
            raise ValueError('Script revision changed within a generation request')
        query = draft.question[:330] + ' Answer: ' + draft.answer[:150]
        hits = await retrieve_script(client, snapshot=snapshot, store=self.store,
                                     query=query, allow_spoilers=True, k=6, hybrid=True)
        script, trace = self.script_evidence(snapshot, hits)
        if not script:
            return None
        return StoryContext([released, *script], {released.alias: context.citations[released.alias]},
            context.script, {**context.trace,
                'wiki_hits': [h for h in context.trace['wiki_hits'] if h['alias'] == released.alias],
                'script_hits': trace, 'script_strategy': 'candidate_question_and_answer_bm25_rrf',
                'target_query_sha256': hashlib.sha256(query.encode()).hexdigest()})

    def audit(self, context, *, mode, decisions, drafts):
        # No full screenplay excerpts or user questions in saved traces.
        atomic_json(self.trace_root/f'{context.trace["movie_id"]}-{uuid4().hex}.json',
            {**context.trace, 'mode': mode, 'decisions': decisions,
             'candidate_sha256': hashlib.sha256(drafts.model_dump_json().encode()).hexdigest(),
             'candidate_count': len(drafts.items)})

    async def discuss(self, client, *, source, passages, question):
        context = await self.context(client, source=source, passages=passages, query=question, script_query=question)
        if context is None:
            return MovieAnswer(status='insufficient_evidence', answer='The available sources do not agree on enough scene context to answer this question.')
        drafts = await propose_story(client, evidence=context.evidence, mode='discussion', question=question)
        decisions = await review_story(client, drafts=drafts, evidence=context.evidence, mode='discussion')
        self.audit(context, mode='discussion', decisions=decisions, drafts=drafts)
        if not drafts.items or not decisions[0]['accepted']:
            return MovieAnswer(status='insufficient_evidence', answer='The available sources do not support a consistent answer to this question.', script_context=context.script)
        item = drafts.items[0]
        answer = ('One possible reading: ' if item.kind == 'interpretation' else '') + item.answer
        return MovieAnswer(status='answered', answer=answer, citations=[context.citations[item.wiki_alias]],
                           answer_kind=item.kind, script_context=context.script)

    async def quiz(self, client, *, source, passages, existing):
        generated = sum(i.id.startswith('script-rag-') for i in existing.items)
        topic = TOPICS['story'][(len(existing.items)+generated) % len(TOPICS['story'])]
        previous = [i.question for i in existing.items]
        coverage = [i.question+' Answer: '+i.options[i.correct_index] for i in existing.items if i.kind != 'interpretation']
        accepted, excluded = [], []
        started = monotonic()
        for attempt in range(2):
            # One verified item per request keeps the route responsive and lets
            # a later request select another uncovered story unit. Start a
            # second window only while enough of the route budget remains.
            if monotonic() - started > 60 or accepted:
                break
            context = None
            try:
                async with asyncio.timeout(110):
                    context = await self.context(client, source=source, passages=passages, query=topic,
                        existing_questions=coverage, excluded_origins=excluded)
                    if context is None:
                        break
                    context.trace['attempt'] = attempt + 1
                    excluded.extend((h['origin']['start'],h['origin']['end']) for h in context.trace['wiki_hits'])
                    seeds = await propose_quiz_seed(client, evidence=[e for e in context.evidence if e.alias.startswith('W')], previous=previous)
                    context.trace['initial_candidate_count'] = len(seeds.items)
                    drafts = StoryDrafts(items=[])
                    if seeds.items:
                        seed_decisions = await review_quiz_seeds(client,seeds=seeds,
                            evidence=[e for e in context.evidence if e.alias.startswith('W')])
                        context.trace['released_seed_review'] = seed_decisions
                        focus_priority = {'turning_point':0,'choice_or_motivation':1,
                            'relationship':2,'ending_or_resolution':3,'story_rule':4,
                            'cause_or_consequence':5,'theme_or_concept':6,'granular_recall':7}
                        eligible = [(seed,decision) for seed,decision in zip(seeds.items,seed_decisions)
                                    if decision['accepted']]
                        eligible.sort(key=lambda item:(
                            0 if item[1]['assessment']['narrative_significance']=='central' else 1,
                            focus_priority[item[1]['assessment']['narrative_focus']]))
                        previous.extend(seed.question for seed,decision in zip(seeds.items,seed_decisions)
                                        if not decision['accepted'])
                        if not eligible:
                            self.audit(context,mode='quiz',decisions=seed_decisions,drafts=drafts)
                            continue
                        script_attempts = []
                        base_context = context
                        for seed,seed_decision in eligible:
                            focused = await self.focus_quiz_context(client, base_context, seed)
                            if focused is None:
                                script_attempts.append({'accepted':False,'reason':'No targeted scene context.'})
                                previous.append(seed.question)
                                continue
                            alias = await select_script_context(client,seed=seed,evidence=focused.evidence)
                            if alias is None:
                                script_attempts.append({'accepted':False,'reason':'No consistent script corroboration.'})
                                previous.append(seed.question)
                                context = focused
                                continue
                            context = focused
                            script_attempts.append({'accepted':True,
                                'focus':seed_decision['assessment']['narrative_focus']})
                            drafts = StoryDrafts(items=[draft_from_seed(seed,evidence=context.evidence,script_alias=alias)])
                            break
                        context.trace['script_seed_attempts'] = script_attempts
                        if not drafts.items:
                            self.audit(context,mode='quiz',decisions=script_attempts,drafts=drafts)
                            continue
                    decisions = await review_story(client, drafts=drafts, evidence=context.evidence, mode='quiz')
                    for item, decision in zip(drafts.items, decisions):
                        duplicate = any(SequenceMatcher(None, normalized(item.question), normalized(text)).ratio() > .72 for text in previous)
                        if duplicate:
                            decision.update(accepted=False, reason='Similar to an existing question.')
                        if not decision['accepted']:
                            previous.append(item.question)
                            continue
                        previous.append(item.question)
                        coverage.append(item.question+' Answer: '+item.answer)
                        accepted.append(QuizItem(id='script-rag-'+uuid4().hex[:12], origin='generated', kind='plot',
                            question=item.question, options=item.options, correct_index=item.correct_index,
                            explanation=item.wiki_quote, citations=[context.citations[item.wiki_alias]]))
                    self.audit(context, mode='quiz', decisions=decisions, drafts=drafts)
            except (ValueError, httpx.HTTPError, TimeoutError) as error:
                if context is not None:
                    self.audit(context, mode='quiz', decisions=[{'accepted':False,'error':type(error).__name__,
                        'reason':'Generation attempt failed validation or exceeded its deadline.'}], drafts=StoryDrafts(items=[]))
        return accepted
