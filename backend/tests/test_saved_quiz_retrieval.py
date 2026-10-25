from movie_companion.evidence_store import SourceDocument
from movie_companion.saved_quiz_retrieval import retrieve_saved_quiz_evidence
from movie_companion.source_sections import SourceSection
from test_content_store import fixture_collection


def test_saved_quiz_terms_prioritize_the_passage_containing_its_answer():
    _,(quiz,_)=fixture_collection();item=next(question for question in quiz.items if question.kind!='interpretation')
    answer=item.options[item.correct_index]
    first='The production used a large practical model during filming.'
    second=f'The story reveals that {answer} is the decisive outcome for the characters.'
    text=first+'\n\n'+second
    source=SourceDocument('wiki-targeted',157336,text,
        'English Wikipedia contributors: Interstellar (film)',
        'https://en.wikipedia.org/w/index.php?oldid=125','enwiki-125-sections-v3-body','unknown',
        (SourceSection(0,len(first)+2,'Production','production'),
         SourceSection(len(first)+2,len(text),'Plot','plot')))
    evidence=retrieve_saved_quiz_evidence(source,quiz,limit=1)
    assert len(evidence)==1 and answer in evidence[0].text
    assert evidence[0].origin.section_category=='plot'
