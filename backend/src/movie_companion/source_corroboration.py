"""Independent released-film check before web-sourced quiz publication."""
from dataclasses import asdict
from .discussion_retrieval import retrieve_discussion_passages
from .discussion_support import review_support,MODEL
from .embedding_learning import embed_texts
from .ingestion_learning import ingest_source
from .web_corpus_store import registered_source_match
from .sentence_spans import complete_sentence_spans
from .discussion_retrieval import _terms


def ranked_independent_sources(*, source, documents, question, answer):
    """Put sources likely to contain the exact answer inside the bounded review window."""
    from .source_coverage import publisher

    original_publisher = publisher(source.source_ref)
    question_terms = set(_terms(question))
    answer_terms = set(_terms(answer))
    references = [
        document.source
        for document in documents
        if document.source.movie_id == source.movie_id
        and registered_source_match(document.source) != "script"
        and publisher(document.source.source_ref) not in (None, original_publisher)
    ]

    def rank(reference):
        source_terms = set(_terms(reference.text))
        plot_source = any(section.category == "plot" for section in reference.sections)
        stable_priority = (
            0 if reference.revision.startswith("enwiki-")
            else 1 if reference.source_id.startswith("tmdb-")
            else 2
        )
        return (
            -len(answer_terms & source_terms),
            -len(question_terms & source_terms),
            -int(plot_source),
            stable_priority,
            reference.source_id,
        )

    return sorted(references, key=rank)


async def review_answer_evidence(client, *, source, passages, question, answer):
    """Return exact source sentences only when this source supports the whole answer."""
    from .movie_questions import QuestionCitation

    supports = {}
    for passage in passages:
        for start, end in complete_sentence_spans(passage.text):
            if 20 <= end - start <= 600:
                supports.setdefault(passage.text[start:end], passage)
    terms = set(_terms(question + " " + answer))
    quotes = sorted(supports, key=lambda quote: -len(terms & set(_terms(quote))))[:5]
    if not quotes:
        return []
    try:
        review = await review_support(client, model=MODEL, question=question, answer=answer, quotes=quotes)
    except ValueError:
        return []
    if review.verdict != "supported":
        return []
    web = registered_source_match(source) == "web"
    return [
        QuestionCitation(
            passage_id=supports[quote].passage_id,
            source_label=source.source_label,
            source_ref=source.source_ref,
            revision=source.revision,
            excerpt=quote,
            source_kind="web" if web else "reviewed",
            source_verified=web,
        )
        for quote in review.evidence_quotes
    ]

async def corroborate_question(client,*,source,documents,store,question,answer):
    references=ranked_independent_sources(source=source,documents=documents,
                                          question=question,answer=answer)
    if not references:return {'status':'unavailable','evidence':[],'review':None}
    vector=None;last=None
    for reference in references[:4]:
        await ingest_source(client,store=store,source=reference,model='nomic-embed-text:v1.5',max_chars=600,overlap_chars=100)
        passages=store.load_snapshot(reference,model='nomic-embed-text:v1.5',max_chars=600,overlap_chars=100)
        if vector is None:vector=(await embed_texts(client,model='nomic-embed-text:v1.5',texts=['search_query: '+question]))[0]
        hits=retrieve_discussion_passages(question=question,query_vector=vector,passages=passages,
            query_model='nomic-embed-text:v1.5',movie_id=source.movie_id,allow_spoilers=True,k=3)
        quotes=list(dict.fromkeys(h.passage.text[a:b] for h in hits
            for a,b in complete_sentence_spans(h.passage.text) if 20<=b-a<=600))
        terms=set(_terms(question+' '+answer));quotes.sort(key=lambda q:-len(terms&set(_terms(q))));quotes=quotes[:5]
        if not quotes:continue
        review=await review_support(client,model=MODEL,question=question,answer=answer,quotes=quotes)
        last={'status':review.verdict,'source_id':reference.source_id,'revision':reference.revision,
              'evidence':quotes,'review':asdict(review)}
        if review.verdict=='supported':return last
    return last or {'status':'unavailable','evidence':[],'review':None}

async def corroborate_answer(client,*,documents,store,movie_id,question,answer,excluded_publishers):
    """Return independent exact citations only after complete-answer support."""
    import asyncio
    from .source_coverage import publisher
    from .movie_questions import QuestionCitation
    references=[d.source for d in documents if d.source.movie_id==movie_id
                and registered_source_match(d.source)!='script'
                and publisher(d.source.source_ref) not in excluded_publishers]
    references.sort(key=lambda s:0 if s.revision.startswith('enwiki-') else 1)
    vector=None
    for reference in references[:3]:
        settings={'model':'nomic-embed-text:v1.5','max_chars':600,'overlap_chars':100}
        await ingest_source(client,store=store,source=reference,**settings)
        passages=await asyncio.to_thread(store.load_snapshot,reference,**settings)
        if vector is None:vector=(await embed_texts(client,model=settings['model'],texts=['search_query: '+question]))[0]
        hits=retrieve_discussion_passages(question=question,query_vector=vector,passages=passages,
            query_model=settings['model'],movie_id=movie_id,allow_spoilers=True,k=3)
        citations=await review_answer_evidence(client,source=reference,
            passages=[hit.passage for hit in hits],question=question,answer=answer)
        if citations:return citations
    return []
