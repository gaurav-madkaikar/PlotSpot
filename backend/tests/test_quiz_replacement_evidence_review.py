import asyncio,json
import httpx

from movie_companion.quiz_replacement_evidence_review import review_evidence


def test_evidence_review_keeps_target_boundaries(monkeypatch):
    async def fake(*args,**kwargs):
        return json.dumps({'items':[{'target_id':'T1','status':'supported','evidence_ids':['E1'],
            'reason':'The passage states the requested consequence explicitly.'}]})
    monkeypatch.setattr('movie_companion.quiz_replacement_evidence_review.chat_once',fake)
    async def run():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',follow_redirects=False) as client:
            return await review_evidence(client,[{'title':'Film','replacement_brief':'Test the consequence.',
                'evidence':[{'excerpt':'The flood destroys the home and displaces the family.'}]}])
    result=asyncio.run(run())
    assert result.items[0].evidence_ids==['E1']


def test_evidence_review_rejects_cross_target_alias(monkeypatch):
    async def fake(*args,**kwargs):
        return json.dumps({'items':[{'target_id':'T1','status':'supported','evidence_ids':['E2'],
            'reason':'This incorrectly selects another target passage.'},
            {'target_id':'T2','status':'insufficient','evidence_ids':[],
             'reason':'No explicit support is present in the supplied passage.'}]})
    monkeypatch.setattr('movie_companion.quiz_replacement_evidence_review.chat_once',fake)
    async def run():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',follow_redirects=False) as client:
            return await review_evidence(client,[
                {'title':'One','replacement_brief':'First relation','evidence':[{'excerpt':'First passage is long enough for review.'}]},
                {'title':'Two','replacement_brief':'Second relation','evidence':[{'excerpt':'Second passage is long enough for review.'}]}])
    try:asyncio.run(run())
    except ValueError:pass
    else:raise AssertionError('Cross-target evidence must fail closed')
