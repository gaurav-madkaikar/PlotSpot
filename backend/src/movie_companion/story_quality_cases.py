"""Resolve pinned, authored real-film evaluation spans without publishing scripts."""
import json

from .evidence_store import SourceDocument
from .proposal_evidence import evidence_pools
from .screenplay_source import SCRIPTS, ScriptSnapshot, scene_sections
from .story_verification import StoryDraft, StoryEvidence


def load_real_cases(path, *, snapshots, scripts):
    if path.stat().st_size > 100_000:
        raise ValueError('Real-film labels exceed the evaluation budget')
    labels = json.loads(path.read_text())['cases']
    if len(labels) != 8 or len({c['id'] for c in labels}) != 8:
        raise ValueError('Require eight distinct preregistered real-film cases')
    cases = []
    for label in labels:
        if type(label['movie_id']) is not int or label['movie_id'] not in SCRIPTS:
            raise ValueError('Unregistered evaluation movie')
        if type(label['expected_accept']) is not bool:
            raise ValueError('Invalid real-film expectation')
        source_path, script_path = snapshots/f'{label["movie_id"]}.json', scripts/f'{label["movie_id"]}.json'
        if source_path.stat().st_size > 1_000_000 or script_path.stat().st_size > 3_000_000:
            raise ValueError('Evaluation source exceeds budget')
        source = SourceDocument(**json.loads(source_path.read_text()))
        script = ScriptSnapshot(**json.loads(script_path.read_text()))
        if (source.movie_id != label['movie_id'] or script.movie_id != label['movie_id']
                or source.revision != label['wiki_revision'] or script.revision != label['script_revision']):
            raise ValueError('Pinned real-film source version mismatch')
        pool = evidence_pools(source)  # checks registered released-film identity
        a,b,c,d = (label[k] for k in ('wiki_start','wiki_end','script_start','script_end'))
        if any(type(n) is not int for n in (a,b,c,d)) or not (0 <= a < b <= len(source.text) and 0 <= c < d <= len(script.text)):
            raise ValueError('Invalid evaluation span')
        if not any(o.start <= a < b <= o.end for _,o in pool['story']):
            raise ValueError('Released-film evaluation span is outside plot evidence')
        if not any(s.start <= c < d <= s.end for s in scene_sections(script.text)):
            raise ValueError('Script evaluation span crosses a scene')
        w,s = source.text[a:b],script.text[c:d]
        evidence = [StoryEvidence(alias='W1',text=w),StoryEvidence(alias='S1',text=s)]
        draft = StoryDraft(**label['draft'],wiki_quote=w,script_quote=s)
        cases.append({'id':label['id'],'mode':'quiz','expected_accept':label['expected_accept'],
                      'draft':draft.model_dump(),'evidence':[e.model_dump() for e in evidence]})
    return cases
