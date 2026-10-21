import pytest

from movie_companion.quiz_narrative_quality import (
    NarrativeCase, NarrativeDataset, NarrativePrediction, advisory_surface_flags,
    narrative_eligible, narrative_surface_blocks, score_predictions,
)


def test_identity_recall_surface_veto_prefers_narrative_rewording():
    assert narrative_surface_blocks('Which crew member kills Cypher?') == ['isolated_identity_recall']
    assert narrative_surface_blocks('Who kills Cypher?') == ['isolated_identity_recall']
    assert narrative_surface_blocks('Why does Cypher betray the crew?') == []
    assert narrative_surface_blocks('What consequence follows Cypher’s betrayal?') == []


def test_generic_action_recall_requires_a_narrative_relation():
    assert narrative_surface_blocks('What action does Angier take regarding the note?') == ['isolated_action_recall']
    assert narrative_surface_blocks('What does Neo do with the red pill?') == ['isolated_action_recall']
    assert narrative_surface_blocks('Why does Angier reject Borden’s note?') == []
    assert narrative_surface_blocks('What consequence follows Neo taking the red pill?') == []


def dataset():
    cases=[]
    for index in range(10):
        cases.append(NarrativeCase(id=f'NQ{index+1:03}',movie='Film',
            question=f'Why does the hero make decision number {index}?',
            expected_focus='choice_or_motivation',expected_significance='central',expected_eligible=True))
    for index in range(10,20):
        cases.append(NarrativeCase(id=f'NQ{index+1:03}',movie='Film',
            question=f'What minor object appears in scene number {index}?',
            expected_focus='granular_recall',expected_significance='granular',expected_eligible=False))
    return NarrativeDataset(policy='plotspot-narrative-quiz-eval-v1',partition='development',cases=cases)


def test_code_owned_gate_accepts_narrative_value_and_rejects_granular_recall():
    assert narrative_eligible('turning_point','central')
    assert narrative_eligible('relationship','supporting')
    assert not narrative_eligible('granular_recall','supporting')
    assert not narrative_eligible('story_rule','granular')
    assert not narrative_eligible('not_applicable','not_applicable')


def test_eval_reports_retention_rejection_and_label_accuracy():
    data=dataset()
    predictions=[NarrativePrediction(id=case.id,focus=case.expected_focus,
        significance=case.expected_significance) for case in data.cases]
    report=score_predictions(data,predictions)
    assert report['metrics']=={
        'useful_retention_percent':100.0,'granular_rejection_percent':100.0,
        'eligibility_accuracy_percent':100.0,'focus_accuracy_percent':100.0,
        'significance_accuracy_percent':100.0}
    predictions[0]=NarrativePrediction(id='NQ001',focus='granular_recall',significance='granular')
    assert score_predictions(data,predictions)['metrics']['useful_retention_percent']==90.0


def test_eval_rejects_missing_duplicate_and_incoherent_labels():
    data=dataset()
    predictions=[NarrativePrediction(id=case.id,focus=case.expected_focus,
        significance=case.expected_significance) for case in data.cases]
    with pytest.raises(ValueError):score_predictions(data,predictions[:-1])
    with pytest.raises(ValueError):score_predictions(data,[*predictions[:-1],predictions[0]])
    with pytest.raises(ValueError):NarrativeCase(id='NQ999',movie='Film',question='Why does the hero leave the city?',
        expected_focus='turning_point',expected_significance='central',expected_eligible=False)


@pytest.mark.parametrize('question,expected',[
    ('How many years does the journey last?',['exact_count_or_duration']),
    ('In which city does the story take place?',['isolated_location']),
    ('What is the name of the minor clerk?',['isolated_name']),
    ('Why does the hero abandon the mission?',[]),
])
def test_surface_flags_are_advisory_and_conservative(question,expected):
    assert advisory_surface_flags(question)==expected
