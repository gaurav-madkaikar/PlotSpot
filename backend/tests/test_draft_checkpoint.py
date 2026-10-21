import importlib.util
import json
from pathlib import Path

import pytest


script_path = Path(__file__).parents[1] / 'scripts' / 'prepare_content_drafts.py'
spec = importlib.util.spec_from_file_location('prepare_content_drafts_script', script_path)
script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(script)


def test_checkpoint_replaces_complete_json_and_cleans_temporary_file(tmp_path):
    path = tmp_path / 'reports' / 'draft.json'
    script.write_checkpoint(path, {'state':'running', 'facts':[]})
    script.write_checkpoint(path, {'state':'incomplete', 'facts':[{'title':'Miniature city'}]})
    assert json.loads(path.read_text())['state'] == 'incomplete'
    assert list(path.parent.glob('.draft-*')) == []


def test_failed_checkpoint_preserves_last_report_and_cleans_temporary_file(tmp_path, monkeypatch):
    path = tmp_path / 'draft.json'
    script.write_checkpoint(path, {'state':'running', 'batches':[1]})
    original = path.read_bytes()
    def fail(*args, **kwargs):
        raise PermissionError('Cannot replace report')
    monkeypatch.setattr(Path, 'replace', fail)
    with pytest.raises(PermissionError):
        script.write_checkpoint(path, {'state':'incomplete', 'batches':[1,2]})
    assert path.read_bytes() == original
    assert list(tmp_path.glob('.draft-*')) == []
