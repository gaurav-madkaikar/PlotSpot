from types import SimpleNamespace

import pytest

from movie_companion.source_coverage import content_coverage, publisher, require_content_coverage


def item(url, *, kind=None):
    values={'citations':[SimpleNamespace(source_ref=url)]}
    if kind is not None:values['kind']=kind
    return SimpleNamespace(**values)


def test_publisher_groups_revisions_subdomains_and_excludes_draft_scripts():
    assert publisher('https://en.wikipedia.org/w/index.php?oldid=1')=='wikipedia.org'
    assert publisher('https://fr.wikipedia.org/wiki/Film')=='wikipedia.org'
    assert publisher('https://www.bbc.co.uk/culture/article')=='bbc.co.uk'
    assert publisher('https://news.bbc.com/story')=='bbc.co.uk'
    assert publisher('https://imsdb.com/scripts/Film.html') is None
    assert publisher('https://film.example.com/story')=='example.com'
    with pytest.raises(ValueError):publisher('not-a-url')


def test_completion_counts_actual_published_items_and_publishers_per_bank():
    facts=SimpleNamespace(items=[item('https://en.wikipedia.org/a') for _ in range(4)]+[item('https://bfi.org.uk/b')])
    quiz=SimpleNamespace(items=[item('https://en.wikipedia.org/a',kind='plot') for _ in range(9)]
        +[item('https://rogerebert.com/reviews/x',kind='plot'),item('https://example.com/opinion',kind='interpretation')])
    coverage=content_coverage(quiz,facts)
    assert coverage['complete'] is True
    assert coverage['facts']=={'items':5,'publishers':['bfi.org.uk','wikipedia.org']}
    assert coverage['quiz']['items']==10 and coverage['quiz']['publishers']==['rogerebert.com','wikipedia.org']
    assert require_content_coverage(quiz,facts)==coverage


def test_each_bank_needs_two_publishers_even_when_the_other_bank_is_diverse():
    facts=SimpleNamespace(items=[item('https://en.wikipedia.org/a') for _ in range(5)])
    quiz=SimpleNamespace(items=[item('https://en.wikipedia.org/a',kind='plot') for _ in range(9)]
        +[item('https://bfi.org.uk/b',kind='plot')])
    assert content_coverage(quiz,facts)['complete'] is False
    with pytest.raises(ValueError,match='at least two publishers'):
        require_content_coverage(quiz,facts)
