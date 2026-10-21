import asyncio

from movie_companion.content_proposals import EvidenceOrigin,ProposalEvidence
from movie_companion.discussion_support import SupportReview
from movie_companion.evidence_store import SourceDocument
from movie_companion.saved_quiz_corroboration import corroborate_saved_question
from movie_companion.source_sections import SourceSection
from movie_companion.web_corpus_store import WebCorpusStore
from test_content_store import fixture_collection


def test_direct_corroboration_saves_one_self_sufficient_sentence(monkeypatch,tmp_path):
    monkeypatch.setenv('PLOTSPOT_WEB_CORPUS_DB',str(tmp_path/'web.db'))
    _,(quiz,_)=fixture_collection();target=next(item for item in quiz.items if item.kind!='interpretation')
    text='The exact outcome in the released story is the answer described by this source.'
    source=SourceDocument('tmdb-157336',157336,text,'The Movie Database (TMDB) · Interstellar',
        'https://www.themoviedb.org/movie/157336','tmdb-details-'+'c'*64+'-v1','unknown',
        (SourceSection(0,len(text),'Overview','plot'),))
    WebCorpusStore().remember(source,'provider')
    evidence=[ProposalEvidence(passage_id='P1',purpose='story',text=text,
        origin=EvidenceOrigin(movie_id=157336,source_id=source.source_id,source_ref=source.source_ref,
            revision=source.revision,section_title='Overview',section_category='plot',start=0,end=len(text)))]
    calls=[]
    async def review(*args,quotes,answer,**kwargs):
        calls.append(quotes)
        return SupportReview('supported','The sentence supports the exact saved answer.',
            answer,tuple(quotes))
    monkeypatch.setattr('movie_companion.saved_quiz_corroboration.review_support',review)
    result=asyncio.run(corroborate_saved_question(None,source=source,evidence=evidence,quiz=quiz))
    assert calls==[[text]]
    assert result['target_id'] in {item.id for item in quiz.items} and result['evidence_quote']==text
    assert result['review']['evidence_quotes']==(text,)
