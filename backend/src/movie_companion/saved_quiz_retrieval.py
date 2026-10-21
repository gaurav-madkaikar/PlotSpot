"""Deterministic evidence windows targeted at an existing scored quiz."""
from .content_proposals import ProposalEvidence
from .discussion_retrieval import _terms
from .proposal_evidence import evidence_pools,verify_origins

POLICY='saved-quiz-lexical-retrieval-v1'


def retrieve_saved_quiz_evidence(source,quiz,*,limit=2):
    if type(limit)is not int or not 1<=limit<=2:raise ValueError('Saved quiz retrieval limit is one or two')
    questions=[item for item in quiz.items if item.kind!='interpretation']
    if not questions:return []
    queries=[set(_terms(item.question+' '+item.options[item.correct_index])) for item in questions]
    ranked=[]
    for text,origin in evidence_pools(source)['story']:
        words=set(_terms(text));score=max((len(words&query) for query in queries),default=0)
        if score:ranked.append((score,origin.start,text,origin))
    ranked.sort(key=lambda row:(-row[0],row[1]))
    selected=ranked[:limit]
    evidence=[ProposalEvidence(passage_id=f'P{i+1}',purpose='story',text=row[2],origin=row[3])
              for i,row in enumerate(selected)]
    verify_origins(source,evidence)
    return evidence
