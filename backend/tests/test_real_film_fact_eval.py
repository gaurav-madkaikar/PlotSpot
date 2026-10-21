import asyncio
import copy
import hashlib
import json
from pathlib import Path
import runpy
from types import SimpleNamespace

import httpx
import pytest

from movie_companion import real_film_fact_eval as evaluation
from movie_companion.content_proposals import ContentProposals
from movie_companion.content_proposal_review import DraftDecision, DraftReview

ROOT = Path(__file__).parents[2]
DATASET = ROOT/'evals/movie-rag/real-film-facts/dataset-v1.json'


def dataset():
    return evaluation.RealFilmDataset.model_validate_json(DATASET.read_text())


def source_fixture(tmp_path):
    data = dataset().model_dump()
    data['sources'] = data['sources'][:1]
    data['quality']['batches'] = data['quality']['batches'][:1]
    identity = data['sources'][0]
    evidence = data['quality']['batches'][0]['evidence'][0]
    origin = evidence['origin']
    origin['start'], origin['end'] = 0, len(evidence['text'])
    source = dict(source_id=origin['source_id'], movie_id=identity['movie_id'], text=evidence['text'],
                  source_label='English Wikipedia contributors: Parasite (2019 film)',
                  source_ref=identity['source_ref'], revision=identity['revision'],
                  sections=[dict(title=origin['section_title'], category=origin['section_category'],
                                 start=0, end=len(evidence['text']))])
    raw = json.dumps(source).encode()
    (tmp_path/f"{identity['movie_id']}.json").write_bytes(raw)
    identity['snapshot_sha256'] = hashlib.sha256(raw).hexdigest()
    path = tmp_path/'dataset.json'
    path.write_text(json.dumps(data))
    return path, data, source


def test_frozen_cases_cover_six_movies_and_eighteen_labels():
    data = dataset()
    assert len(data.sources) == len(data.quality.batches) == 6
    labels = [label.decision for b in data.quality.batches for label in b.labels.values()]
    assert labels.count('accept') == 6 and labels.count('reject') == 12
    # Avoid a benchmark made from the same already-published snippets.
    for batch in data.quality.batches:
        mid = batch.evidence[0].origin.movie_id
        bank = json.loads((ROOT/f'backend/src/movie_companion/content_banks/{mid}.json').read_text())
        for fact in bank['facts']:
            assert not any(marker in batch.evidence[0].text for marker in fact['evidence_markers'])


@pytest.mark.parametrize('change', ['missing-origin', 'story-purpose', 'wrong-movie', 'duplicate-source',
                                  'missing-source', 'quiz', 'held-out'])
def test_invalid_coverage_rejected(change):
    data = dataset().model_dump()
    batch = data['quality']['batches'][0]
    if change == 'missing-origin': batch['evidence'][0]['origin'] = None
    elif change == 'story-purpose': batch['evidence'][0]['purpose'] = 'story'
    elif change == 'wrong-movie': batch['evidence'][0]['origin']['movie_id'] = 999
    elif change == 'duplicate-source': data['sources'].append(copy.deepcopy(data['sources'][0]))
    elif change == 'missing-source': data['sources'].pop()
    elif change == 'quiz': batch['proposals']['facts'] = []; batch['labels'] = {}
    else: data['quality']['partition'] = 'held-out'
    with pytest.raises(ValueError): evaluation.RealFilmDataset.model_validate(data)


def test_verified_source_round_trip(tmp_path):
    path, data, _ = source_fixture(tmp_path)
    assert evaluation.load_dataset(path, tmp_path).model_dump() == data


@pytest.mark.parametrize('change', ['hash', 'span', 'text', 'revision', 'source-ref', 'movie', 'label'])
def test_tampering_fails_before_any_inference(tmp_path, change):
    path, data, source = source_fixture(tmp_path)
    identity = data['sources'][0]
    evidence = data['quality']['batches'][0]['evidence'][0]
    if change == 'hash': identity['snapshot_sha256'] = '0'*64
    elif change == 'span': evidence['origin']['start'] = 1
    elif change == 'text': evidence['text'] += ' Altered evidence.'
    else:
        if change == 'revision': source['revision'] = 'enwiki-1-sections-v3-body'
        elif change == 'source-ref': source['source_ref'] = 'https://example.org/unregistered'
        elif change == 'movie': source['movie_id'] = 999
        else: source['source_label'] = 'Invented publisher'
        raw = json.dumps(source).encode()
        (tmp_path/f"{identity['movie_id']}.json").write_bytes(raw)
        identity['snapshot_sha256'] = hashlib.sha256(raw).hexdigest()
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError): evaluation.load_dataset(path, tmp_path)


def test_writer_receives_evidence_without_labels_and_no_publication(monkeypatch):
    data = dataset()
    seen = []
    async def writer(client, evidence, previous):
        assert previous == []
        seen.append(evidence)
        return ContentProposals(facts=[], questions=[])
    async def critic(client, **kwargs):
        return DraftReview(items=[])
    monkeypatch.setattr(evaluation.workflow, 'propose_article_facts', writer)
    monkeypatch.setattr(evaluation, 'review_proposals', critic)
    report = asyncio.run(evaluation.inspect_generation(None, dataset=data))
    assert len(seen) == 6 and report['state'] == 'complete'
    assert report['observations'] == dict(completed_movies=6, error_movies=0,
                                       proposed_facts=0, eligible_drafts=0)
    assert report['publication_approved'] is False
    assert 'content_store' not in Path(evaluation.__file__).read_text().lower()


@pytest.mark.parametrize('failure', ['http', 'malformed', 'deadline'])
def test_inspection_errors_preserve_all_six_films(monkeypatch, failure):
    async def writer(*args):
        if failure == 'http': raise httpx.ReadTimeout('Local timeout')
        if failure == 'malformed': raise ValueError('Invalid writer response')
        raise TimeoutError('Overall deadline')
    monkeypatch.setattr(evaluation.workflow, 'propose_article_facts', writer)
    report = asyncio.run(evaluation.inspect_generation(None, dataset=dataset()))
    assert len(report['movies']) == 6 and report['observations']['error_movies'] == 6
    assert report['observations']['eligible_drafts'] == 0
    assert report['state'] == ('incomplete' if failure == 'deadline' else 'complete')


def test_critic_acceptance_cannot_override_copied_prose_gate(monkeypatch):
    data = dataset()
    async def writer(client, evidence, previous):
        return ContentProposals(facts=[dict(title='An editing detail', text=evidence[0].text,
            passage_id='P1', evidence_quote=evidence[0].text)], questions=[])
    async def critic(client, **kwargs):
        return DraftReview(items=[DraftDecision(item_id='F1', decision='accept',
                                               reason='Mock acceptance to check the independent prose gate.')])
    monkeypatch.setattr(evaluation.workflow, 'propose_article_facts', writer)
    monkeypatch.setattr(evaluation, 'review_proposals', critic)
    report = asyncio.run(evaluation.inspect_generation(None, dataset=data))
    first = report['movies'][0]['decisions'][0]
    assert first['decision'] == 'accept' and 'copied_prose' in first['problems']
    assert first['eligible_draft'] is False


def test_cli_refuses_existing_report_before_loading_or_inference(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'backend/scripts'))
    runner = runpy.run_path(str(ROOT/'backend/scripts/evaluate_real_film_facts.py'))
    output = tmp_path/'report.json'
    output.write_text('previous outcomes')
    args = SimpleNamespace(output=output, dataset=tmp_path/'missing.json', snapshots=tmp_path,
                           deadline_seconds=1)
    with pytest.raises(ValueError, match='new JSON report'):
        asyncio.run(runner['main'](args))
    assert output.read_text() == 'previous outcomes'


def test_incomplete_critic_output_is_not_eligible(monkeypatch):
    async def writer(client, evidence, previous):
        return ContentProposals(facts=[dict(title='A paraphrased editing detail',
            text='The edit sometimes combined different takes within the same shot.',
            passage_id='P1', evidence_quote=evidence[0].text)], questions=[])
    async def critic(client, **kwargs):
        return DraftReview(items=[])
    monkeypatch.setattr(evaluation.workflow, 'propose_article_facts', writer)
    monkeypatch.setattr(evaluation, 'review_proposals', critic)
    report = asyncio.run(evaluation.inspect_generation(None, dataset=dataset()))
    assert report['observations']['error_movies'] == 6
    assert report['observations']['eligible_drafts'] == 0
    assert report['observations']['proposed_facts'] == 6


def test_critic_cannot_approve_fragmented_initial_quote(monkeypatch):
    data=dataset()
    data.quality.batches=[b for b in data.quality.batches if b.evidence[0].origin.movie_id==129]
    async def writer(client,evidence,previous):
        text=evidence[0].text
        return ContentProposals(facts=[dict(title='Dialogue fitted to animation',
            text='The writers fitted English dialogue to the original animated lip movements.',
            passage_id='P1',evidence_quote=text[text.index('Hewitt penned'):])],questions=[])
    async def critic(client,**kwargs):
        return DraftReview(items=[DraftDecision(item_id='F1',decision='accept',
                                               reason='Mock approval reproducing the earlier incomplete citation.')])
    monkeypatch.setattr(evaluation.workflow,'propose_article_facts',writer)
    monkeypatch.setattr(evaluation,'review_proposals',critic)
    report=asyncio.run(evaluation.inspect_generation(None,dataset=data))
    decision=report['movies'][0]['decisions'][0]
    assert decision['decision']=='accept'
    assert 'incomplete_support_quote' in decision['problems']
    assert decision['eligible_draft'] is False


def test_generation_only_does_not_infer_or_report_labelled_scores(monkeypatch):
    async def forbidden(*args,**kwargs):
        pytest.fail('Labelled inference is excluded in generation-only mode')
    async def generation(*args,**kwargs):
        return {'state':'complete','movies':[],'publication_approved':False}
    monkeypatch.setattr(evaluation,'evaluate_quality',forbidden)
    monkeypatch.setattr(evaluation,'inspect_generation',generation)
    report=asyncio.run(evaluation.evaluate_real_facts(None,dataset=dataset(),generation_only=True))
    assert report['mode']=='generation-only' and report['state']=='complete'
    assert 'quality' not in report and report['publication_approved'] is False
