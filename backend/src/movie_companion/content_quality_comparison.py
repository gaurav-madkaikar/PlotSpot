"""Compare compatible critic observations without inventing a publication gate."""
from .content_quality_eval import metrics


def compare_quality(baseline, revised, held_out):
    reports = [baseline,revised,held_out]
    if any(r.get('state')!='complete' for r in reports):
        raise ValueError('Compare only completed runs; keep failed cases in their metrics')
    if [r['partition'] for r in reports] != ['development','development','held-out']:
        raise ValueError('Compare development baselines with a separate reserved partition')
    for field in ('model_digest','model','generation_settings'):
        if any(r[field]!=baseline[field] for r in reports):
            raise ValueError('Model and generation settings must match')
    if baseline['dataset_sha256']!=revised['dataset_sha256']:
        raise ValueError('Development dataset changed; scores are not comparable')
    if held_out['dataset_sha256']==revised['dataset_sha256']:
        raise ValueError('Held-out dataset must be separate')
    def cases(report):
        result={r['case_id']:r for r in report['cases']}
        if len(result)!=len(report['cases']):
            raise ValueError('Duplicate case identities')
        return result
    old,new,reserved=map(cases,reports)
    if set(old)!=set(new) or set(new)&set(reserved):
        raise ValueError('Case identities must match within development and differ in held-out')
    for key in old:
        if any(old[key][field]!=new[key][field] for field in ('expected','category')):
            raise ValueError('Expected labels changed between development runs')
    baseline_metrics, candidate_metrics = metrics(baseline['cases']), metrics(revised['cases'])
    candidate_selected = (
        candidate_metrics['false_acceptance']['count'] <= baseline_metrics['false_acceptance']['count']
        and candidate_metrics['useful_acceptance']['count'] >= baseline_metrics['useful_acceptance']['count']
        and candidate_metrics['label_matches']['count'] >= baseline_metrics['label_matches']['count']
        and candidate_metrics['errors']['count'] == 0
    )
    selected = revised if candidate_selected else baseline
    for field in ('critic_policy_version','critic_implementation_sha256'):
        if held_out[field]!=selected[field]:
            raise ValueError('Evaluate the selected frozen critic on reserved cases')
    return {
        'selected_policy':selected['critic_policy_version'],
        'candidate_selected':candidate_selected,
        'selection_rule':'Candidate must not increase false approvals, reduce useful approvals or label matches, '
                         'and must have zero evaluation errors on the same development cases.',
        'baseline':{'policy':baseline['critic_policy_version'],'metrics':metrics(baseline['cases']),
                    'elapsed_seconds':baseline['elapsed_seconds']},
        'revised':{'policy':revised['critic_policy_version'],'metrics':metrics(revised['cases']),
                   'elapsed_seconds':revised['elapsed_seconds']},
        'held_out':{'policy':held_out['critic_policy_version'],'metrics':metrics(held_out['cases']),
                    'elapsed_seconds':held_out['elapsed_seconds']},
        'development_changes':[{'case_id':key,'expected':new[key]['expected'],
                               'before':old[key]['actual'],'after':new[key]['actual']}
                              for key in old if old[key]['actual']!=new[key]['actual']],
        'held_out_mismatches':[r for r in held_out['cases'] if not r['matched']],
        'publication_approved':False,
        'limitations':'Small authored synthetic sets; no automatic production-quality gate. '
                      'Policy selected using development results only. No tuning against reserved results in this comparison. '
                      'Historical metric names are normalized from unchanged case decisions.'}
