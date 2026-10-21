import asyncio,json
import httpx,pytest
from movie_companion import research_generation as writer
from movie_companion.proposal_evidence import evidence_batches
from test_movie_research import story_document,background_document
from movie_companion.content_proposals import EvidenceOrigin,ProposalEvidence

def test_writer_receives_saved_topics_and_maps_code_owned_quote(monkeypatch):
    source=story_document().source;seen=[]
    async def chat(*args,**kwargs):
        seen.append(kwargs['prompt'])
        assert kwargs['max_output_tokens']==1536
        return json.dumps({'items':[{'support_id':'S1','question':'What does Louise discover about her memories?',
            'options':['Visions of the future','Army simulations','Dreams','Alien childhood'], 'correct_index':0}]})
    monkeypatch.setattr(writer,'chat_once',chat)
    async def call():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            return await writer.generate_batch(client,source=source,movie_title='Arrival',purpose='story',
                evidence=evidence_batches(source,max_batches=1)[0],
                existing_questions=[{'question':'How many craft arrive?','answer':'Twelve'}],existing_facts=[])
    result=asyncio.run(call())
    assert result.questions[0].evidence_quote==source.text
    assert 'How many craft arrive?' in seen[0]
    assert 'isolated recall' in seen[0] and 'turning points' in seen[0]
    assert 'Pick an unused\ndetail: a location, object, number' not in seen[0]
    assert result.facts==[]


def test_background_writer_sees_only_complete_support_sentences(monkeypatch):
    source=background_document().source;s=source.sections[0]
    origin=EvidenceOrigin(movie_id=source.movie_id,source_id=source.source_id,source_ref=source.source_ref,
        revision=source.revision,section_title=s.title,section_category=s.category,start=0,end=len(source.text))
    evidence=[ProposalEvidence(passage_id='P1',purpose='background',text=source.text,origin=origin)]
    async def chat(*args,**kwargs):
        data=json.loads(kwargs['prompt'].split('Return only the requested JSON.\n',1)[1])
        assert data['context']==[]
        assert data['support_options'] and all(set(option)=={'support_id','text'} for option in data['support_options'])
        return json.dumps({'items':[]})
    monkeypatch.setattr(writer,'chat_once',chat)
    async def call():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            return await writer.generate_batch(client,source=source,movie_title='Arrival',purpose='background',
                evidence=evidence,existing_questions=[],existing_facts=[])
    assert asyncio.run(call()).facts==[]

@pytest.mark.parametrize('raw',[{'items':[{'support_id':'S99','title':'A physical chamber','text':'A physical chamber replaced green screen work.'}]},
    {'items':[{'support_id':'S1','title':'A physical chamber','text':'A physical chamber replaced green screen work.','question':'Wrong role'}]}])
def test_unknown_support_or_cross_role_fields_fail(monkeypatch,raw):
    source=background_document().source;s=source.sections[0]
    origin=EvidenceOrigin(movie_id=source.movie_id,source_id=source.source_id,source_ref=source.source_ref,
        revision=source.revision,section_title=s.title,section_category=s.category,start=0,end=len(source.text))
    evidence=[ProposalEvidence(passage_id='P1',purpose='background',text=source.text,origin=origin)]
    async def chat(*args,**kwargs):return json.dumps(raw)
    monkeypatch.setattr(writer,'chat_once',chat)
    async def call():
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434') as client:
            with pytest.raises(ValueError):await writer.generate_batch(client,source=source,movie_title='Arrival',purpose='background',evidence=evidence,existing_questions=[],existing_facts=[])
    asyncio.run(call())
