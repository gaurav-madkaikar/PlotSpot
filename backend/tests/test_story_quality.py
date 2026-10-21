from dataclasses import asdict
import importlib.util
import json
from pathlib import Path

import pytest

from movie_companion.local_models import DIGESTS
from movie_companion.story_quality_cases import load_real_cases
from movie_companion.story_verification import MODEL, POLICY
from test_content_evidence_retrieval import fixture_source
from test_screenplay_ingestion import snapshot


def gate_module():
    spec = importlib.util.spec_from_file_location('story_gate_eval',Path(__file__).parents[1]/'scripts/evaluate_story_gate.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_qualification_rejects_old_code_and_errored_inspections(tmp_path):
    module = gate_module()
    report = tmp_path/'inspection.json'
    record = {'policy':POLICY,'model':MODEL,'model_digest':DIGESTS[MODEL],'implementation_sha256':'current',
        'published':False,'totals':{'errors':0,'attempt_errors':0},'movies':[{'movie_id':603,'accepted':[]}]}
    report.write_text(json.dumps(record))
    assert module.quiz_qualifications(report,'current')[0] == []
    for patch in [{'implementation_sha256':'older'}, {'published':True}, {'totals':{'errors':0,'attempt_errors':1}}]:
        report.write_text(json.dumps({**record,**patch}))
        with pytest.raises(ValueError,match='match'):
            module.quiz_qualifications(report,'current')


def test_gate_can_resolve_a_versioned_dataset_family(tmp_path):
    module = gate_module()
    dataset = tmp_path/'narrative-v1'
    real_cases = tmp_path/'real-narrative-v1.json'
    paths,resolved_real = module.evaluation_paths(dataset,real_cases)
    assert paths == [dataset/'development.json',dataset/'reserved.json',dataset/'adversarial.json']
    assert resolved_real == real_cases


def test_real_case_references_cannot_change_source_version_or_cross_scene(tmp_path):
    source,script = fixture_source(),snapshot()
    roots = tmp_path/'wiki',tmp_path/'scripts'
    for root in roots:root.mkdir()
    (roots[0]/'27205.json').write_text(json.dumps(asdict(source)))
    (roots[1]/'27205.json').write_text(json.dumps(asdict(script)))
    scene = script.text.index('INT. CLOCK ROOM')
    end = script.text.index('EXT. GARDEN')
    labels = [{'id':f'case-{i}','movie_id':27205,'expected_accept':True,
        'wiki_revision':source.revision,'script_revision':script.revision,
        'wiki_start':0,'wiki_end':len(source.text.splitlines()[0]),'script_start':scene,'script_end':end,
        'draft':{'kind':'event','question':'Which map does Lena return to the keeper?',
            'answer':'map number 0','wiki_alias':'W1','script_alias':'S1',
            'options':['map number 0','map number 1','map number 2','map number 3'],'correct_index':0}}
        for i in range(8)]
    path = tmp_path/'labels.json'
    def load():return load_real_cases(path,snapshots=roots[0],scripts=roots[1])
    path.write_text(json.dumps({'cases':labels}))
    assert len(load()) == 8
    labels[0]['script_revision'] = 'another-version'
    path.write_text(json.dumps({'cases':labels}))
    with pytest.raises(ValueError,match='version'):load()
    labels[0]['script_revision'] = script.revision
    labels[0]['script_end'] = end+1
    path.write_text(json.dumps({'cases':labels}))
    with pytest.raises(ValueError,match='scene'):load()
