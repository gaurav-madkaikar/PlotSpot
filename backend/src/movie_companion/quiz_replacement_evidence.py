"""Bounded lexical retrieval for saved-quiz replacement briefs."""

from collections import Counter
import math
import re

from .movie_web_sources import MovieIdentity
from .quiz_replacement_completion import NarrativeIntent
from .sentence_spans import complete_sentence_spans
from .source_coverage import publisher


POLICY = 'quiz-replacement-evidence-bm25-v1'
STOP = frozenset('''a an the is are was were be been do does did what which who where
when how why with to for from in on at of as and or that this his her their they it
movie film story question replace replacement broader evidence exact omit ask about
instead rather based objective'''.split())


def terms(text):
    return [word for word in re.findall(r"[a-z0-9]+",text.casefold())
            if len(word)>2 and word not in STOP]


def story_sentences(source):
    rows=[]
    for section in source.sections:
        if section.category!='plot':continue
        body=source.text[section.start:section.end]
        for start,end in complete_sentence_spans(body):
            sentence=body[start:end].strip()
            if 20<=len(sentence)<=600:
                rows.append((section.title,sentence))
                if len(rows)>=2000:return rows
    return rows


def targeted_story_query(movie:MovieIdentity,intent:NarrativeIntent,*,revision:int):
    """Build two bounded discovery queries from reviewed target language."""
    movie=movie if isinstance(movie,MovieIdentity) else MovieIdentity(**movie)
    intent=intent if isinstance(intent,NarrativeIntent) else NarrativeIntent.model_validate(intent)
    if revision not in (1,2):raise ValueError('Only an initial and one revised query are allowed')
    concepts=[group[0] if revision==1 else group[-1] for group in intent.required_concepts]
    title=re.sub(r'[^\w .,:!?()\-]',' ',movie.title)[:160]
    variant='plot explanation' if revision==1 else 'story analysis'
    query=' '.join((f'"{title}"',str(movie.year or ''),'film',intent.relation,
                    intent.focus,*concepts,variant))
    query=' '.join(query.split())
    if len(query)>500:raise ValueError('Targeted story query exceeds budget')
    return query


def retrieve_replacement_evidence(store, target, *, intent=None, limit=8):
    """Rank complete plot sentences; ranking is relevance, not proof."""
    if type(limit) is not int or not 1<=limit<=8:
        raise ValueError('Invalid replacement evidence limit')
    query=' '.join((target['replacement_brief'],target['old_question'],
                    target['evidence'].get('explanation','')))
    if intent is not None:
        intent=intent if isinstance(intent,NarrativeIntent) else NarrativeIntent.model_validate(intent)
        if intent.question_id!=target.get('question_id',intent.question_id):
            raise ValueError('Narrative intent crossed target boundaries')
        query=' '.join((query,intent.focus,intent.relation,
                        *(alias for group in intent.required_concepts for alias in group)))
    query_terms=set(terms(query))
    candidates=[]
    sources=store.movie_sources(target['movie_id'],kinds=('web','script','provider'))
    for source,kind in sources:
        for section_title,sentence in story_sentences(source):
            candidates.append({'source':source,'kind':kind,'section_title':section_title,
                               'text':sentence,'tokens':Counter(terms(sentence))})
            if len(candidates)>=8000:raise ValueError('Replacement evidence corpus budget exceeded')
    if not candidates or not query_terms:
        return [],{'policy':POLICY,'movie_sources':len(sources),'candidate_sentences':len(candidates),
                  'query_terms':sorted(query_terms),'ranked':0}
    frequency=Counter(word for candidate in candidates for word in candidate['tokens'])
    average=sum(sum(candidate['tokens'].values()) for candidate in candidates)/len(candidates) or 1
    for candidate in candidates:
        length=sum(candidate['tokens'].values());score=0.
        for word in query_terms:
            count=candidate['tokens'][word]
            if count:
                idf=math.log(1+(len(candidates)-frequency[word]+.5)/(frequency[word]+.5))
                score+=idf*count*2.2/(count+1.2*(.25+.75*length/average))
        candidate['score']=score
    ordered=sorted((item for item in candidates if item['score']>0),
                   key=lambda item:(-item['score'],item['source'].source_id,item['text']))
    selected=[];seen=set();per_source=Counter();per_publisher=Counter()
    for item in ordered:
        source=item['source'];key=(source.revision,item['text'])
        host=publisher(source.source_ref)
        if key in seen or per_source[source.source_id]>=2 or host and per_publisher[host]>=2:continue
        seen.add(key);per_source[source.source_id]+=1
        if host:per_publisher[host]+=1
        selected.append({'source_id':source.source_id,'source_label':source.source_label,
            'source_ref':source.source_ref,'revision':source.revision,
            'section_title':item['section_title'],'excerpt':item['text'],
            'bm25':round(item['score'],6),'publisher':host,'source_kind':item['kind']})
        if len(selected)==limit:break
    return selected,{'policy':POLICY,'movie_sources':len(sources),
        'candidate_sentences':len(candidates),'query_terms':sorted(query_terms),
        'ranked':len(ordered),'selected':len(selected)}
