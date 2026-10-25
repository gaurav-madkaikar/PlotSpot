"""Small authored critic-development suite; not a general safety benchmark."""
import argparse
import asyncio
import json
from pathlib import Path
from time import monotonic

import httpx

from movie_companion.content_proposals import ContentProposals, ProposalEvidence
from movie_companion.content_proposal_review import review_proposals
from movie_companion.local_models import DIGESTS, verify_local_model


async def main(args):
    dataset = json.loads(args.dataset.read_text())
    evidence = [ProposalEvidence.model_validate(e) for e in dataset['evidence']]
    proposals = ContentProposals.model_validate(dataset['proposals'])
    started = monotonic()
    async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',timeout=120,
                                trust_env=False,follow_redirects=False) as client:
        async with asyncio.timeout(140):
            await verify_local_model(client,args.model)
            result = await review_proposals(client,model=args.model,proposals=proposals,evidence=evidence)
    actual = {item.item_id:item for item in result.items}
    cases = [{'item_id':item_id,'expected':label['decision'],'category':label['category'],
              'actual':actual[item_id].decision,'matched':actual[item_id].decision==label['decision'],
              'reason':actual[item_id].reason} for item_id,label in dataset['labels'].items()]
    report = {'model':args.model,'model_digest':DIGESTS[args.model],'dataset':str(args.dataset),
              'partition':'authored-development','elapsed_seconds':round(monotonic()-started,2),
              'matched':sum(case['matched'] for case in cases),'total':len(cases),'cases':cases,
              'limitations':'Six authored cases in one batch; not held out, not a general injection or content-quality benchmark. No tool or publication permissions.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',type=Path,default=Path('evals/movie-rag/content-review-cases.json'))
    parser.add_argument('--output',type=Path,default=Path('evals/movie-rag/content-review-ollama.json'))
    parser.add_argument('--model',choices=['llama3.2:3b','qwen3.5:9b'],default='qwen3.5:9b')
    asyncio.run(main(parser.parse_args()))
