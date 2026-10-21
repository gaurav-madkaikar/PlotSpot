"""Offline labelled acquisition-policy eval; no model or network calls."""
import argparse
import json
from pathlib import Path
from movie_companion.movie_web_sources import MovieIdentity,make_web_source
from movie_companion.public_web import WebRead


def evaluate(dataset):
    rows=[]
    for case in dataset['cases']:
        identity=MovieIdentity(**case['movie'])
        try:
            source=make_web_source(identity,WebRead(case['url'],case['html'].encode(), 'text/html'),purpose=case['purpose'])
            actual='accept'
            # Verify the result's allowed route rather than treating nonempty text
            # or similarity as a proxy for the purpose label.
            categories={s.category for s in source.sections}
            if case['purpose']=='story' and categories!={'plot'}:actual='wrong_route'
            if case['purpose']=='background' and not categories<= {'production','casting','filming','music','effects'}:actual='wrong_route'
        except ValueError:actual='reject'
        rows.append({'id':case['id'],'expected':case['expected'],'actual':actual,'passed':actual==case['expected']})
    return {'dataset':dataset['name'],'case_count':len(rows),'passed':sum(r['passed'] for r in rows),
            'scope':'Authored offline acquisition/routing cases; not live search quality or model accuracy.','cases':rows}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--dataset',type=Path,required=True);parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();report=evaluate(json.loads(args.dataset.read_text()))
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(f"{report['passed']}/{report['case_count']} labelled acquisition-policy cases passed")
    raise SystemExit(0 if report['passed']==report['case_count'] else 1)
