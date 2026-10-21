"""Retrieve broader pinned story evidence for unresolved quiz replacements."""

import argparse
from datetime import datetime,timezone
import json
from pathlib import Path

from movie_companion.preparation_jobs import atomic_json
from movie_companion.quiz_replacement_evidence import POLICY,retrieve_replacement_evidence
from movie_companion.research_checkpoint import digest
from movie_companion.web_corpus_store import WebCorpusStore


def main(args):
    candidates=json.loads(args.candidates.read_text())
    review=json.loads(args.review.read_text())
    if (candidates.get('status')!='proposal_only' or candidates.get('published') is not False
            or review.get('status')!='proposal_only' or review.get('published') is not False):
        raise ValueError('Expected non-publishing replacement inputs')
    by_id={item['question_id']:item for item in candidates['items']}
    store=WebCorpusStore(args.corpus)
    rows=[]
    for decision in review['items']:
        if decision['final_review']=='accept':continue
        source=by_id[decision['question_id']]
        evidence,trace=retrieve_replacement_evidence(store,source,limit=args.limit)
        rows.append({'movie_id':source['movie_id'],'title':source['title'],
            'question_id':source['question_id'],'old_question':source['old_question'],
            'replacement_brief':source['replacement_brief'],'previous_result':decision['final_review'],
            'evidence':evidence,'retrieval':trace})
    report={'generated_at':datetime.now(timezone.utc).isoformat(),'policy':POLICY,
        'status':'proposal_only','published':False,
        'candidate_report_sha256':digest(candidates),'editorial_review_sha256':digest(review),
        'corpus':str(args.corpus),'summary':{'targets':len(rows),
            'targets_with_evidence':sum(bool(row['evidence']) for row in rows),
            'sources_considered':sum(row['retrieval']['movie_sources'] for row in rows),
            'sentences_considered':sum(row['retrieval']['candidate_sentences'] for row in rows)},
        'items':rows,'publication':{'authorized':False,'database_mutated':False}}
    atomic_json(args.output,report)
    print(json.dumps(report['summary'],indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidates',type=Path,required=True)
    parser.add_argument('--review',type=Path,required=True)
    parser.add_argument('--corpus',type=Path,default=Path('data/private/web-corpus.db'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--limit',type=int,default=8,choices=range(1,9))
    main(parser.parse_args())
