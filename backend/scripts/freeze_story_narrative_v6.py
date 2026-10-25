"""Freeze an unseen real-film narrative holdout before running the v18 reviewer."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import shutil

from movie_companion.evidence_store import SourceDocument
from movie_companion.preparation_jobs import atomic_json
from movie_companion.screenplay_source import ScriptSnapshot, scene_sections
from movie_companion.story_quality_cases import load_real_cases

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
WIKI = ROOT/'.cache/source-snapshots'
SCRIPTS = BACKEND/'data/private/screenplays'
FAMILY = ROOT/'evals/movie-rag/cross-source-narrative-v6'
REAL = ROOT/'evals/movie-rag/story-quality/real-movie-cases-narrative-v4.json'


CASES = [
    dict(id='narrative-v4-jules-retirement', movie_id=680, expected_accept=True,
         wiki_start=5777, wiki_end=5916, script_start=117526, script_end=118450,
         label_reason='The apparent miracle motivates Jules to leave crime, a central character choice.',
         draft=dict(kind='event', question='What belief convinces Jules to retire from his life of crime?',
             answer='their survival at the apartment was divine intervention', wiki_alias='W1', script_alias='S1',
             options=['their survival at the apartment was divine intervention',
                      'Marsellus had forgiven every debt he owed', 'Vincent planned to leave Los Angeles with him',
                      'the diner robbery had exposed their briefcase'], correct_index=0)),
    dict(id='narrative-v4-mia-overdose', movie_id=680, expected_accept=True,
         wiki_start=6323, wiki_end=6908, script_start=49377, script_end=50350,
         label_reason='This tests the direct consequence of a consequential story mistake.',
         draft=dict(kind='event', question="What consequence follows Mia mistaking Vincent's heroin for cocaine?",
             answer='She passes out from an overdose', wiki_alias='W1', script_alias='S1',
             options=['She passes out from an overdose', 'She reports Vincent to Marsellus',
                      'She leaves the house to find Lance', 'She challenges Vincent to another dance'], correct_index=0)),
    dict(id='narrative-v4-butch-rescue', movie_id=680, expected_accept=True,
         wiki_start=7562, wiki_end=7919, script_start=107732, script_end=108400,
         label_reason='Butch choosing to intervene changes both his and Marsellus’s outcomes.',
         draft=dict(kind='event', question='What does Butch do after breaking free in the pawnshop?',
             answer='kills Maynard with a katana, freeing Marsellus', wiki_alias='W1', script_alias='S1',
             options=['kills Maynard with a katana, freeing Marsellus', 'abandons Marsellus and calls the police',
                      'takes Zed hostage and waits for Vincent', 'returns the gold watch to Maynard'], correct_index=0)),
    dict(id='narrative-v4-borden-method', movie_id=1124, expected_accept=True,
         wiki_start=5362, wiki_end=5940, script_start=150798, script_end=151197,
         label_reason='The twins’ shared identity is the central story rule behind the illusion.',
         draft=dict(kind='event', question='How do the two Bordens perform The Transported Man?',
             answer='switching places undetected', wiki_alias='W1', script_alias='S1',
             options=['switching places undetected', 'using Tesla’s duplication machine',
                      'hiding Root beneath the stage', 'escaping through a concealed water tank'], correct_index=0)),
    dict(id='narrative-v4-granular-wolfe-name', movie_id=680, expected_accept=False,
         wiki_start=5281, wiki_end=5776, script_start=110300, script_end=110641,
         label_reason='This is isolated identity recall even though both sources identify the cleaner.',
         draft=dict(kind='event', question='Who does Marsellus send to help clean the car?',
             answer='Winston Wolfe', wiki_alias='W1', script_alias='S1',
             options=['Winston Wolfe', 'Jimmie', 'Pumpkin', 'Lance'], correct_index=0)),
    dict(id='narrative-v4-generic-olivia-action', movie_id=1124, expected_accept=False,
         wiki_start=3287, wiki_end=3883, script_start=103560, script_end=104500,
         label_reason='The generic action stem reduces a central rivalry to isolated action recall.',
         draft=dict(kind='event', question='What action does Angier take regarding Olivia?',
             answer='he sends Olivia to spy on him', wiki_alias='W1', script_alias='S1',
             options=['he sends Olivia to spy on him', 'he dismisses her from the theatre',
                      'he asks her to build a new machine', 'he sends her to protect Sarah'], correct_index=0)),
    dict(id='narrative-v4-wrong-mia-cause', movie_id=680, expected_accept=False,
         wiki_start=6323, wiki_end=6908, script_start=49377, script_end=50350,
         label_reason='Revival is a later response to the overdose, not the reason Mia collapses.',
         draft=dict(kind='event', question='Why does Mia pass out after returning home?',
             answer='they revive her by injecting her heart with adrenaline', wiki_alias='W1', script_alias='S1',
             options=['they revive her by injecting her heart with adrenaline',
                      "she mistakes Vincent's heroin for cocaine", 'Vincent leaves her alone at the restaurant',
                      'Marsellus orders her to conceal the briefcase'], correct_index=0)),
    dict(id='narrative-v4-uncorroborated-tesla-warning', movie_id=1124, expected_accept=False,
         wiki_start=3885, wiki_end=4385, script_start=150798, script_end=151197,
         label_reason='The released account contains Tesla’s warning, while the pinned excerpt describes another event.',
         draft=dict(kind='event', question='What does Tesla warn Angier about the machine?',
             answer='it will bring only misery', wiki_alias='W1', script_alias='S1',
             options=['it will bring only misery', 'it can transport only one person',
                      'it will fail outside Colorado', 'it requires Borden to operate it'], correct_index=0)),
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    targets = [REAL, *(FAMILY/name for name in ('development.json','reserved.json','adversarial.json','preregistration.json'))]
    if any(path.exists() for path in targets):
        raise ValueError('The v6 holdout family is immutable and already exists')
    labels = []
    for case in CASES:
        source = SourceDocument(**json.loads((WIKI/f'{case["movie_id"]}.json').read_text()))
        script = ScriptSnapshot(**json.loads((SCRIPTS/f'{case["movie_id"]}.json').read_text()))
        a,b,c,d = (case[key] for key in ('wiki_start','wiki_end','script_start','script_end'))
        if not any(section.category == 'plot' and section.start <= a < b <= section.end for section in source.sections):
            raise ValueError(f'{case["id"]}: released span is not plot evidence')
        if not any(section.start <= c < d <= section.end for section in scene_sections(script.text)):
            raise ValueError(f'{case["id"]}: screenplay span crosses a scene')
        record = {**case, 'wiki_revision':source.revision, 'script_revision':script.revision}
        labels.append(record)
    REAL.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(REAL, {'kind':'preregistered_narrative_real_movie_holdout_v4',
                       'created_at':'2026-10-21', 'cases':labels})
    FAMILY.mkdir(parents=True)
    previous = ROOT/'evals/movie-rag/cross-source-narrative-v5'
    for name in ('development.json','reserved.json','adversarial.json'):
        shutil.copyfile(previous/name, FAMILY/name)
    # Validate exact revisions, source categories, screenplay scenes and schemas
    # before the preregistration can be marked unconsumed.
    load_real_cases(REAL, snapshots=WIKI, scripts=SCRIPTS)
    files = [FAMILY/name for name in ('development.json','reserved.json','adversarial.json')]
    hashes = {str(path.relative_to(ROOT)):digest(path) for path in [*files,REAL]}
    atomic_json(FAMILY/'preregistration.json', {
        'policy_intent':'narrative-first cross-source qualification on unseen films and events',
        'frozen_at':'2026-10-21', 'execution_state':'unconsumed',
        'partitions':{'development':8,'reserved':8,'adversarial':4,'real_movies':8},
        'thresholds':{'false_approvals':0,'minimum_useful_acceptance':0.75,'errors':0},
        'notes':['Synthetic partitions are unchanged safety regressions.',
                 'The real-film partition was frozen before reviewer execution.',
                 'Positive cases cover motivation, consequence, rescue and a central story rule.',
                 'Negative cases cover identity recall, action recall, wrong causality and missing corroboration.'],
        'sha256':hashes,
    })
    print(f'Frozen and validated {len(labels)} real-film cases in {FAMILY.name}.')


if __name__ == '__main__':
    main()
