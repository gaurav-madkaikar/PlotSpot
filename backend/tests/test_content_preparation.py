import asyncio
import copy
from dataclasses import replace

import httpx
import pytest

from movie_companion import content_preparation as pipeline
from movie_companion.content_proposals import ContentProposals, check_proposals
from movie_companion.content_proposal_review import DraftDecision, DraftReview
from movie_companion.evidence_store import SourceDocument
from movie_companion.proposal_evidence import evidence_batches, verify_origins
from movie_companion.source_sections import SourceSection


def source():
    plot = '\n'.join(f'Lena returns map number {i} to the lighthouse keeper before dawn.' for i in range(16))
    filming = '\n'.join(f'The crew builds miniature lighthouse number {i} inside a water tank.' for i in range(16))
    music = '\n'.join(f'The composer records piano theme number {i} in an empty warehouse.' for i in range(8))
    text = plot+'\n'+filming+'\n'+music
    return SourceDocument(source_id='wiki_27205', movie_id=27205, text=text,
        source_label='English Wikipedia contributors: Inception',
        source_ref='https://en.wikipedia.org/w/index.php?oldid=123', revision='enwiki-123-sections-v3-body',
        sections=(SourceSection(0,len(plot)+1,'Plot','plot'),
                  SourceSection(len(plot)+1,len(plot)+len(filming)+2,'Filming','filming'),
                  SourceSection(len(plot)+len(filming)+2,len(text),'Music','music')))


def test_adapter_derives_purpose_keeps_exact_offsets_and_varies_background_sections():
    batches = evidence_batches(source())
    assert len(batches) == 8
    for batch in batches:
        verify_origins(source(), batch)
        assert [e.passage_id for e in batch] == ['P1','P2','P3','P4']
        assert [e.purpose for e in batch] == ['story','story','background','background']
    assert [e.origin.section_title for e in batches[0][2:]] == ['Filming', 'Music']


@pytest.mark.parametrize('change', ['missing-sections','wrong-title','wrong-url','wrong-revision','unknown-movie'])
def test_adapter_rejects_unclassified_or_wrong_source_identity(change):
    changes = {'missing-sections': {'sections':()}, 'wrong-title':{'source_label':'Other film'},
               'wrong-url':{'source_ref':'https://evil.example'}, 'wrong-revision':{'revision':'v1'},
               'unknown-movie':{'movie_id':999999999}}
    with pytest.raises(ValueError): evidence_batches(replace(source(), **changes[change]))


@pytest.mark.parametrize('field,value', [('purpose','background'), ('text','A substituted source sentence with wrong offsets.')])
def test_tampered_passages_fail_against_actual_source(field, value):
    passage = evidence_batches(source())[0][0].model_copy(update={field:value})
    with pytest.raises(ValueError): verify_origins(source(), [passage])


def test_plot_section_cannot_be_claimed_as_fact_by_changing_purpose():
    passage = evidence_batches(source())[0][0].model_copy(update={'purpose':'background'})
    proposal = ContentProposals.model_validate({'facts':[{'title':'A secret map', 'text':passage.text,
        'passage_id':'P1', 'evidence_quote':passage.text}], 'questions':[]})
    assert check_proposals(proposal,[passage])[0]['problems'] == ['wrong_source_section']


def test_missing_classification_and_overlong_sentence_are_not_forced_into_context():
    original = source()
    long_text = 'A'+(' very long' * 100)+'.'
    modified = replace(original, text=long_text, sections=(SourceSection(0,len(long_text),'Plot','plot'),))
    with pytest.raises(ValueError): evidence_batches(modified)
    modified = replace(original, sections=(SourceSection(0,len(original.text),'Reception','other'),))
    with pytest.raises(ValueError): evidence_batches(modified)


def mock_models(monkeypatch, *, repeat=False, fail_at=None, decisions='accept'):
    calls = []
    async def generate(client, *, evidence, **kwargs):
        calls.append('generate')
        if fail_at == calls.count('generate'):
            raise ValueError('Invalid model JSON')
        batch = calls.count('generate')
        facts, questions = [], []
        for p in evidence:
            if p.purpose == 'background':
                facts.append({'title':f'Miniature method {batch}', 'text':p.text,
                              'passage_id':p.passage_id, 'evidence_quote':p.text})
            else:
                questions.append({'question':f'Which map number {batch} does Lena return in scene {p.passage_id}?',
                    'options':['A map','A letter','A diary','A compass'], 'correct_index':0,
                    'passage_id':p.passage_id,'evidence_quote':p.text})
        return ContentProposals.model_validate({'facts':facts[:2], 'questions':questions[:2]})
    async def review(client, *, proposals, **kwargs):
        calls.append('review')
        return DraftReview(items=[DraftDecision(item_id=f'{prefix}{i+1}', decision=decisions,
            reason='Mocked labelled judgement for orchestration only.')
            for prefix, items in [('F',proposals.facts),('Q',proposals.questions)] for i,_ in enumerate(items)])
    monkeypatch.setattr(pipeline, 'propose_content', generate)
    monkeypatch.setattr(pipeline, 'review_proposals', review)
    # Exact wording duplicates intentionally bypassed in the success fixture;
    # their behavior has separate assertions below.
    if not repeat:
        monkeypatch.setattr(pipeline, 'duplicate_reason', lambda *args: None)
    return calls


def run(**kwargs):
    return asyncio.run(pipeline.prepare_drafts(None, source=source(), model='test', review_model='test', **kwargs))


def test_targets_stop_calls_and_checkpoints_keep_provenance_without_publication(monkeypatch):
    calls = mock_models(monkeypatch)
    snapshots = []
    report = run(checkpoint=lambda r: snapshots.append(copy.deepcopy(r)))
    assert report['state'] == 'needs_review'
    assert len(report['facts']) == 5 and len(report['questions']) == 10
    assert len(calls) == 10  # five generator + five critic calls, never unbounded
    assert len(snapshots) == 17 and snapshots[0]['state'] == 'running'
    assert {'retrieving','generating','reviewing','finished'} <= {s['phase'] for s in snapshots}
    assert report['facts'][0]['origin']['section_category'] == 'filming'
    assert not report['publication_approved'] and not report['saved_collection_changed']


def test_budget_exhaustion_does_not_fill_quota_and_uncertain_is_not_accepted(monkeypatch):
    calls = mock_models(monkeypatch, decisions='uncertain')
    report = run(max_batches=2)
    assert report['state'] == 'incomplete' and len(calls) == 4
    assert not report['facts'] and not report['questions']
    assert report['stop_reason'] == 'evidence_or_batch_budget_exhausted'


def test_failed_later_batch_preserves_completed_drafts_and_stops(monkeypatch):
    calls = mock_models(monkeypatch, fail_at=2)
    report = run()
    assert report['state'] == 'incomplete' and len(report['batches']) == 1
    assert len(report['facts']) == 2 and len(calls) == 3
    assert report['error_type'] == 'ValueError'
    assert report['stop_reason'] == 'model_or_validation_failure'


def test_timeout_is_bounded_and_records_partial_state(monkeypatch):
    async def timeout(*args, **kwargs):
        raise httpx.ReadTimeout('Local inference timeout')
    monkeypatch.setattr(pipeline, 'propose_content', timeout)
    assert run()['stop_reason'] == 'model_or_validation_failure'


def test_cross_batch_duplicates_are_filtered():
    previous = [{'question':'Where does Lena leave the map before dawn?', 'evidence_quote':'The same supporting quotation.'}]
    assert pipeline.duplicate_reason(previous[0], previous, 'question') == 'overlapping_wording'
    changed = {'question':'Who receives the map from the visitor?', 'evidence_quote':previous[0]['evidence_quote']}
    assert pipeline.duplicate_reason(changed, previous, 'question') == 'reused_evidence_quote'


def test_stops_when_remaining_evidence_cannot_supply_missing_questions(monkeypatch):
    calls = mock_models(monkeypatch)
    original = source()
    background = original.text[original.sections[1].start:original.sections[1].end]
    background_only = replace(original, text=background,
        sections=(SourceSection(0,len(background),'Filming','filming'),))
    report = asyncio.run(pipeline.prepare_drafts(None, source=background_only,
        model='test', review_model='test'))
    assert len(report['facts']) == 5 and report['questions'] == []
    assert len(calls) == 6 and len(report['batches']) == 3
    assert report['stop_reason'] == 'no_evidence_for_unmet_targets'
    assert report['state'] == 'incomplete'


def test_optional_verifier_is_used_and_recorded_without_publication(monkeypatch):
    calls=mock_models(monkeypatch)
    async def reject_all(*args,proposals,**kwargs):
        return DraftReview(items=[DraftDecision(item_id=f'{prefix}{i+1}',decision='reject',
            reason='Injected verifier rejects every draft for this contract test.')
            for prefix,items in [('F',proposals.facts),('Q',proposals.questions)] for i,_ in enumerate(items)])
    report=run(max_batches=1,reviewer=reject_all)
    assert calls==['generate']
    assert report['facts']==[] and report['questions']==[]
    assert report['verifier_module']==reject_all.__module__
    assert not report['publication_approved']


@pytest.mark.parametrize('kwargs', [{'max_batches':0}, {'max_batches':9}, {'max_batches':True},
                                   {'deadline_seconds':0}, {'deadline_seconds':601}])
def test_invalid_budgets_fail_before_model_calls(kwargs):
    with pytest.raises(ValueError): run(**kwargs)


def test_retrieval_loader_trace_checkpoint_and_existing_generator_composition(monkeypatch):
    from movie_companion.content_evidence_retrieval import RetrievedEvidence
    calls = mock_models(monkeypatch)
    async def load():
        return RetrievedEvidence(evidence_batches(source(), max_batches=1), {'version':'fixture-rag'})
    snapshots = []
    report = run(max_batches=1, evidence_loader=load,
                 checkpoint=lambda r: snapshots.append(copy.deepcopy(r)))
    assert calls == ['generate', 'review']
    assert report['evidence_mode'] == 'rag'
    assert snapshots[1]['retrieval'] == {'version':'fixture-rag'}
    assert snapshots[1]['batches'] == []
    assert len(report['facts']) == 2 and len(report['questions']) == 2
    assert not report['saved_collection_changed']


def test_failed_retrieval_stops_before_generation_and_keeps_checkpoint(monkeypatch):
    calls = mock_models(monkeypatch)
    async def load():
        raise httpx.ReadTimeout('Embedding inference failed')
    report = run(evidence_loader=load)
    assert calls == []
    assert report['state'] == 'incomplete'
    assert report['stop_reason'] == 'model_or_validation_failure'


def test_tampered_retrieval_origin_stops_before_generation(monkeypatch):
    from movie_companion.content_evidence_retrieval import RetrievedEvidence
    calls = mock_models(monkeypatch)
    async def load():
        batch = evidence_batches(source(), max_batches=1)[0]
        batch[0] = batch[0].model_copy(update={'text':'This is substituted malicious evidence.'})
        return RetrievedEvidence([batch], {})
    report = run(max_batches=1, evidence_loader=load)
    assert not calls
    assert report['error_type'] == 'ValueError'
