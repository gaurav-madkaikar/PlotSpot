from fastapi.testclient import TestClient
import pytest
from movie_companion.catalog import load_catalog
from movie_companion.catalog_search import CatalogQuery, search_catalog, correct_terms
from movie_companion.catalog_store import CatalogStore
from movie_companion.main import app
from movie_companion.settings import get_settings


def search(query='', **kwargs):
    return search_catalog(load_catalog(), CatalogQuery(query=query, **kwargs), demo=True)


@pytest.mark.parametrize('query,ids,kind', [
    ('Interstellar', [157336], 'title_cast'), ('Intersteler',[157336],'typo'),
    ('Amy Admas',[329865],'typo'), ('Amy Adams',[329865],'title_cast'),
    ('Christopher Nolan',[27205,157336],'title_cast'),
    ('Cristopher Nolan',[27205,157336],'typo'),
    ('movies directed by Christopher Nolan',[27205,157336],'title_cast'),
    ('Movies starring Amy Adams',[329865],'title_cast'),
    ('linguist',[329865],'keyword'), ('linguistt',[329865],'typo'),
    ('pasta recipes and knitting',[],'keyword'), ('quirky charming hotel adventure',[],'keyword'),
])
def test_keyword_title_people_description_and_typos(query, ids, kind):
    result=search(query)
    assert [m.id for m in result.items]==ids
    assert result.match_type==kind


def test_word_boundaries_all_terms_filters_and_no_theme_inference():
    movie=load_catalog()[0].model_copy(update={'title':'Night Journey','director':'Mira Chen',
        'cast':['Ana Cruz'],'genres':['Drama'],'overview':'A courier delivers a letter to a hotel.'})
    for query,total in [('Mira hotel',1),('courier hotel',1),('courier aliens',0),('award',0),('hero movies',0)]:
        assert search_catalog([movie],CatalogQuery(query=query)).total==total
    assert search_catalog([movie],CatalogQuery(query='Ana Cruz',genre='Action')).total==0
    assert search('Intersteler',max_runtime=120).total==0


def test_exact_identity_ranked_before_description_match_and_title_not_stripped():
    first,second=load_catalog()[:2]
    movies=[first.model_copy(update={'title':'The One','overview':'An expedition.'}),
            second.model_copy(update={'overview':'The one person left behind.'})]
    assert search_catalog(movies,CatalogQuery(query='The One')).items[0].id==first.id


def test_ambiguous_typo_not_automatically_guessed():
    assert correct_terms(['stare'], {'spare','stale'}) is None
    first,second=load_catalog()[:2]
    movies=[m.model_copy(update={'title':title,'overview':'','cast':[],'director':None,'genres':[]})
            for m,title in [(first,'Spare'),(second,'Stale')]]
    assert search_catalog(movies,CatalogQuery(query='Stare')).items==[]


def test_stable_unique_pages_and_bounds():
    pages=[search(page=p,page_size=3) for p in range(1,5)]
    assert [len(p.items) for p in pages]==[3,3,3,1]
    assert len({m.id for p in pages for m in p.items})==10
    assert all(p.total==10 and p.total_pages==4 for p in pages)
    assert search(page=5,page_size=3).items==[]


@pytest.mark.parametrize('params',[{'page':0},{'page_size':41},{'q':'x'*301},{'page':10001}])
def test_endpoint_pagination_bounds(params):
    assert TestClient(app).get('/api/search/catalog',params=params).status_code==422


def test_demo_api_search_does_not_require_an_inference_service():
    with TestClient(app) as client:
        assert not hasattr(app.state,'discovery')
        result=client.get('/api/search/catalog',params={'q':'linguist'}).json()
        assert [m['id'] for m in result['items']]==[329865]
        assert result['match_type']=='keyword'


def test_sqlite_catalog_and_new_movies_searchable_without_vector_index(tmp_path,monkeypatch):
    store=CatalogStore(tmp_path/'movies.db')
    movie=load_catalog()[0].model_copy(update={'source':'tmdb','title':'Newly Found',
        'director':'Unique Director','cast':['Unique Actor'],'overview':'A courier explores a lighthouse.'})
    store.upsert_movie(movie,fetched_at='2026-10-11T10:00:00+00:00')
    monkeypatch.setattr(get_settings(),'data_source','tmdb')
    monkeypatch.setattr(app.state,'catalog_store',store,raising=False)
    from movie_companion.unified_discovery import UnifiedDiscovery
    monkeypatch.setattr(app.state,'unified_discovery',UnifiedDiscovery(None,store),raising=False)
    for query in ['Newly Found','Unique Actor','Unique Director','lighthouse']:
        response=TestClient(app).get('/api/search/catalog',params={'q':query})
        assert response.status_code==200 and response.json()['items'][0]['id']==movie.id


def test_tied_localized_title_aliases_share_identity_and_beat_description_typo():
    first,second=load_catalog()[:2]
    movies=[first.model_copy(update={'title':'Interstellar','alternative_titles':['Interestelar']}),
        second.model_copy(update={'title':'Other film','overview':'An intersteller trip.'})]
    result=search_catalog(movies,CatalogQuery(query='Intersteler'))
    assert result.items[0].id==first.id
    assert result.matched_query=='Interstellar'
    assert second.id not in [m.id for m in result.items]


def test_ambiguous_identity_suggestions_do_not_fall_back_to_description_spelling():
    first,second,third=load_catalog()[:3]
    movies=[first.model_copy(update={'title':'Star Love','alternative_titles':[],'overview':''}),
        second.model_copy(update={'title':'Star Cove','alternative_titles':[],'overview':''}),
        third.model_copy(update={'title':'Another film','overview':'Star loves adventures.'})]
    result=search_catalog(movies,CatalogQuery(query='Star Dove'))
    assert result.items==[] and result.matched_query is None


def test_name_fragments_start_at_word_boundaries():
    movie=load_catalog()[0].model_copy(update={'title':'The Award','director':'Ron Howard',
        'cast':['Edward Norton'],'genres':['Drama'],'overview':'A ceremony in a hotel.'})
    assert search_catalog([movie],CatalogQuery(query='war')).items==[]
    assert search_catalog([movie],CatalogQuery(query='Howard')).items[0].id==movie.id


@pytest.mark.parametrize('query', ['Interstell', 'Interstellar'])
def test_title_completion_beats_long_titles_and_alternative_title_fragments(query):
    template = load_catalog()[0]
    movies = [template.model_copy(update={'id': i, 'title': title, 'alternative_titles': aliases})
              for i, title, aliases in [(1, 'Angry Planet', ['Interstellar Combat']),
                  (2, 'Container Interstellar', []), (3, 'Interstellar Wars', []),
                  (4, 'Interstellar', [])]]
    result = search_catalog(movies, CatalogQuery(query=query, page_size=1))
    assert result.items[0].title == 'Interstellar'
    assert result.total == 4


def test_browsing_order_does_not_depend_on_missing_people_metadata():
    first, second = load_catalog()[:2]
    movies = [first.model_copy(update={'title': 'Alpha', 'cast': [], 'director': None}),
              second.model_copy(update={'title': 'Zebra'})]
    assert [m.title for m in search_catalog(movies, CatalogQuery()).items] == ['Alpha', 'Zebra']
