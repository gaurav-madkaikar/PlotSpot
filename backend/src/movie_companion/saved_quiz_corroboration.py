"""Find one independently supported citation for an existing scored question."""
from dataclasses import asdict

from .content_proposals import EvidenceOrigin
from .discussion_retrieval import _terms
from .discussion_support import review_support, MODEL
from .sentence_spans import complete_sentence_spans
from .source_coverage import item_publishers, publisher
from .web_corpus_store import registered_source_match

POLICY='saved-quiz-corroboration-v1'


async def corroborate_saved_question(client,*,source,evidence,quiz,max_reviews=4):
    scored=[item for item in quiz.items if item.kind!='interpretation']
    if (not scored or registered_source_match(source)=='script'
            or publisher(source.source_ref) in item_publishers(scored)):
        return None
    sentences={}
    for passage in evidence:
        if passage.origin is None:continue
        for start,end in complete_sentence_spans(passage.text):
            quote=passage.text[start:end]
            if 20<=len(quote)<=600:sentences.setdefault(quote,(passage,start,end))
    if not sentences:return None
    ranked=[]
    for item in scored:
        terms=set(_terms(item.question+' '+item.options[item.correct_index]))
        best=max((len(terms&set(_terms(quote))) for quote in sentences),default=0)
        ranked.append((best,item.id,item,terms))
    ranked.sort(key=lambda row:(-row[0],row[1]))
    for _,_,item,terms in ranked[:max_reviews]:
        # A citation amendment must stand on one exact sentence. Supplying a
        # bundle here could let the verdict depend on context we do not save.
        quotes=sorted(sentences,key=lambda quote:(-len(terms&set(_terms(quote))),quote))[:1]
        support=await review_support(client,model=MODEL,question=item.question,
            answer=item.options[item.correct_index],quotes=quotes)
        if support.verdict!='supported' or not support.evidence_quotes:continue
        quote=support.evidence_quotes[0];passage,start,end=sentences[quote]
        origin=passage.origin
        exact=EvidenceOrigin(movie_id=origin.movie_id,source_id=origin.source_id,
            source_ref=origin.source_ref,revision=origin.revision,
            section_title=origin.section_title,section_category=origin.section_category,
            start=origin.start+start,end=origin.start+end)
        return {'policy':POLICY,'target_id':item.id,'question':item.question,
            'options':item.options,'correct_index':item.correct_index,
            'passage_id':passage.passage_id,'evidence_quote':quote,
            'origin':exact.model_dump(),'review':asdict(support)}
    return None
