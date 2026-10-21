"""One human-reviewed background claim. No model-generated claims are published."""
from .external_sources import ArticleSnapshot, ScriptProvenance
from .movie_facts import MovieFact, ReadingSource
from .movie_questions import QuestionCitation
from .source_registry import CALTECH_URL

FACT_ID = 'renderer-became-research'
SUPPORT = 'Following the completion of the movie, the code was adapted for scientific research, leading to new insights into gravitational lensing.'


def compile_external_fact(article: ArticleSnapshot):
    source = article.source
    if source.movie_id != 157336 or source.source_ref != CALTECH_URL or SUPPORT not in source.text or 'DNGR (Double Negative Gravitational Renderer)' not in source.text:
        raise ValueError('Reviewed renderer claim lacks supporting evidence')
    start = source.text.index(SUPPORT)
    citation = QuestionCitation(passage_id='caltech-dngr-' + article.content_sha256[:32], source_label=source.source_label,
                                source_ref=source.source_ref, revision=source.revision, excerpt=source.text[start:start + len(SUPPORT)])
    return MovieFact(id=FACT_ID, title='A movie renderer became a research tool',
                     text='The DNGR renderer built for Interstellar was later adapted for scientific research, producing new insights into gravitational lensing, according to the visual-effects team’s published account.', citations=[citation])


def reading_sources(article: ArticleSnapshot, script: ScriptProvenance):
    if script.movie_id != article.source.movie_id or script.eligible_for_quiz:
        raise ValueError('Unexpected screenplay provenance')
    return [ReadingSource(kind='research', title='The science behind the visuals', source_ref=article.source.source_ref,
                          publisher='CaltechAUTHORS · ' + article.publisher, date=article.published_at, authors=list(article.authors),
                          note='A published account from the visual-effects team.', retrieved_at=article.retrieved_at, content_sha256=article.content_sha256),
            ReadingSource(kind='early_draft', title='Interstellar screenplay', source_ref=script.source_ref, publisher='IMSDb',
                          date=script.draft_date, note='Early draft. Story details differ from the released film.', retrieved_at=script.retrieved_at, content_sha256=script.content_sha256)]
