import copy

import pytest

from movie_companion.content_quality_comparison import compare_quality


def reports():
    base={'state':'complete','partition':'development','model':'local','model_digest':'same',
        'generation_settings':{'seed':7},'dataset_sha256':'dev','critic_policy_version':'v1',
        'critic_implementation_sha256':'old','elapsed_seconds':1,
        'cases':[{'case_id':'dev:F1','expected':'reject','category':'metadata','actual':'accept','matched':False}]}
    revised=copy.deepcopy(base)
    revised.update(critic_policy_version='v2',critic_implementation_sha256='new')
    revised['cases'][0].update(actual='reject',matched=True)
    reserved=copy.deepcopy(revised)
    reserved.update(partition='held-out',dataset_sha256='reserved')
    reserved['cases'][0]['case_id']='reserved:F1'
    return base,revised,reserved


def test_comparison_normalizes_metrics_from_decisions_and_preserves_changes():
    result=compare_quality(*reports())
    assert result['baseline']['metrics']['false_acceptance']=={'count':1,'total':1}
    assert result['revised']['metrics']['false_acceptance']=={'count':0,'total':1}
    assert result['development_changes']==[{'case_id':'dev:F1','expected':'reject','before':'accept','after':'reject'}]
    assert not result['publication_approved']
    assert result['candidate_selected'] and result['selected_policy']=='v2'


def test_regressed_candidate_is_not_selected_and_reserved_run_must_match_baseline():
    base,revised,reserved=reports()
    base['cases'][0].update(actual='reject',matched=True)
    revised['cases'][0].update(actual='accept',matched=False)
    reserved.update(critic_policy_version='v1',critic_implementation_sha256='old')
    result=compare_quality(base,revised,reserved)
    assert not result['candidate_selected'] and result['selected_policy']=='v1'
    reserved.update(critic_policy_version='v2',critic_implementation_sha256='new')
    with pytest.raises(ValueError): compare_quality(base,revised,reserved)


@pytest.mark.parametrize('field,value,index',[
    ('state','incomplete',0),('model_digest','different',1),('generation_settings',{'seed':8},2),
    ('dataset_sha256','changed',1),('dataset_sha256','dev',2),
    ('critic_policy_version','v3',2),('critic_implementation_sha256','modified',2),
    ('partition','development',2),
])
def test_incompatible_runs_cannot_be_compared(field,value,index):
    data=list(reports()); data[index][field]=value
    with pytest.raises(ValueError): compare_quality(*data)


@pytest.mark.parametrize('change',['labels','duplicates','overlap'])
def test_changed_labels_or_duplicate_case_identities_are_rejected(change):
    data=list(reports())
    if change=='labels': data[1]['cases'][0]['expected']='accept'
    elif change=='duplicates': data[1]['cases'].append(copy.deepcopy(data[1]['cases'][0]))
    else: data[2]['cases'][0]['case_id']='dev:F1'
    with pytest.raises(ValueError): compare_quality(*data)
