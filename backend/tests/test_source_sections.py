from dataclasses import asdict, replace
import pytest

from movie_companion.evidence_store import EvidenceStore, SourceDocument, snapshot_key
from movie_companion.source_sections import SourceSection, source_chunks, section_for_chunk, routed_chunks
from movie_companion.wikipedia_source import map_article_response
from movie_companion.prepared_content import compile_collection
from test_content_store import fixture_collection


def article(html):
    return map_article_response({'parse': {'title': 'Interstellar (film)', 'pageid': 1, 'revid': 2, 'text': html}}, movie_id=157336, expected_title='Interstellar (film)')


def test_sections_inherit_only_from_parent_and_keep_unknown_spoilers():
    source = article('<p>Intro.</p><h2><span>Plot</span></h2><p>The ending.</p><h2>Production</h2><h3>Development</h3><p>The budget.</p><h3>Practical methods</h3><p>A camera.</p><h2>Reception</h2><p>A review.</p>')
    assert [(s.title, s.category) for s in source.sections] == [
        ('Introduction', 'other'), ('Plot', 'plot'), ('Production', 'production'),
        ('Development', 'production'), ('Practical methods', 'production'), ('Reception', 'other')]
    assert source.spoiler_status == 'unknown'
    assert 'The ending.' in ''.join(c.text for c in routed_chunks(source, purpose='story'))
    background = ''.join(c.text for c in routed_chunks(source, purpose='background'))
    assert 'A camera.' in background and 'The ending.' not in background and 'A review.' not in background
    assert source == SourceDocument(**asdict(source))


def test_chunks_do_not_cross_section_boundaries_even_with_overlap():
    source = article('<h2>Plot</h2><p>Story text continues for a while.</p><h2>Cast</h2><p>An actor plays a part.</p>')
    chunks = source_chunks(source, max_chars=20, overlap_chars=10)
    assert all(c.text == source.text[c.start:c.end] for c in chunks)
    assert all(section_for_chunk(source, c) for c in chunks)
    assert all('Cast' not in c.text for c in routed_chunks(source, purpose='story', max_chars=20, overlap_chars=10))


@pytest.mark.parametrize('sections', [
    [SourceSection(1, 5, 'Plot', 'plot')],
    [SourceSection(0, 3, 'Plot', 'plot'), SourceSection(2, 5, 'Cast', 'casting')],
    [SourceSection(0, 9, 'Plot', 'plot')],
    [SourceSection(0, 3, 'Plot', 'plot')],
])
def test_invalid_spans_rejected(sections):
    with pytest.raises(ValueError):
        SourceDocument('s', 1, 'hello', 'label', 'fixture://s', 'v1', sections=sections)


def test_section_metadata_persists_and_changes_invalidate_snapshot(tmp_path):
    source = article('<h2>Plot</h2><p>The ending.</p><h2>Music</h2><p>The score.</p>')
    settings = dict(model='test', max_chars=30, overlap_chars=5)
    chunks = source_chunks(source, max_chars=30, overlap_chars=5)
    store = EvidenceStore(tmp_path)
    store.save_snapshot(source, chunks, [[1., .5] for _ in chunks], **settings)
    passages = EvidenceStore(tmp_path).load_snapshot(source, **settings)
    assert [p.section_category for p in passages] == ['plot', 'music']
    assert [p.section_title for p in passages] == ['Plot', 'Music']
    changed = replace(source, sections=tuple(replace(s, category='other') for s in source.sections))
    assert snapshot_key(source, **settings) != snapshot_key(changed, **settings)
    assert not store.contains_snapshot(changed, **settings)


@pytest.mark.parametrize('wrong_category', ['plot', 'production', 'other'])
def test_compiler_fails_when_story_or_background_has_wrong_route(wrong_category):
    source, _ = fixture_collection()
    changed = replace(source, sections=tuple(replace(s, category=wrong_category) for s in source.sections))
    with pytest.raises(ValueError, match='Missing supporting'):
        compile_collection(changed)


def test_sectionless_source_cannot_prepare_new_content():
    source, _ = fixture_collection()
    with pytest.raises(ValueError, match='section-aware'):
        compile_collection(replace(source, sections=()))
