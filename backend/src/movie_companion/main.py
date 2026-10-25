import os
import asyncio
import sqlite3
from datetime import timedelta
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path as FilePath
from typing import Annotated, Literal

import httpx
from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from .account_routes import router as account_router, require_user, csrf_check, discovery_preferences
from .account_preferences import AccountPreferences
from .account_boundary import AccountBoundary, member_path
from .history_routes import router as history_router
from .community_routes import router as community_router
from .accounts import AccountStore,AccountError

from .request_logging import configure_request_logging
from .catalog_store import CatalogStore
from .name_search import NameSearchRequest, NameSearchResult, search_names
from .movie_details import load_movie_details
from .movie_extras import WatchOptions, WatchRegions, RelatedMovies
from .movie_extras_store import MovieExtrasStore, load_extra
from .catalog_search import CatalogQuery, search_catalog
from .unified_discovery import UnifiedDiscovery
from .catalog import get_movie, search_movies, load_catalog
from .schemas import Movie, MovieSearchResponse, SuggestionResponse
from .search_suggestions import SuggestionIndex, get_suggestion_index
from .catalog_index import SavedCatalogIndex
from .settings import get_settings
from .tmdb_client import ProviderError, TmdbClient
from .movie_questions import MovieAnswer, MovieQuestion, MovieQuestionService, QuestionError
from .movie_quiz import MovieQuiz
from .movie_facts import MovieFacts
from .movie_features import MovieFeatures, movie_features
from .content_store import ContentStore
from .quiz_generation import generate_more, select_targets, can_expand_quiz
from .story_rag import StoryRag
from pydantic import BaseModel, StrictBool
from .research_jobs import ResearchPreparationJobs
from .preparation_routes import router as preparation_router
from .lab_routes import router as lab_router
from .lab_runs import LabRunReader
from .lab_service import LabService
from .wikipedia_source import MOVIE_ARTICLES


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_request_logging()
    settings = get_settings()
    app.state.accounts = await asyncio.to_thread(AccountStore.configured)
    app.state.catalog_store = await asyncio.to_thread(CatalogStore) if settings.data_source == "tmdb" else None
    async with httpx.AsyncClient(
        base_url="https://api.themoviedb.org/3", timeout=8,
        headers={"Authorization": f"Bearer {settings.tmdb_read_token}"},
        follow_redirects=False, limits=httpx.Limits(max_connections=4),
    ) as http:
        app.state.tmdb = TmdbClient(http, suggestion_index=get_suggestion_index())
        app.state.unified_discovery = UnifiedDiscovery(app.state.tmdb if settings.tmdb_read_token else None,
                                               app.state.catalog_store)
        async with AsyncExitStack() as stack:
            wiki = await stack.enter_async_context(httpx.AsyncClient(
                base_url="https://en.wikipedia.org", timeout=30, follow_redirects=False,
                trust_env=False, headers={"User-Agent": "MovieCompanionLearning/0.1 (local educational source reader)"},
            ))
            ollama = await stack.enter_async_context(httpx.AsyncClient(
                base_url="http://127.0.0.1:11434", timeout=120,
                follow_redirects=False, trust_env=False,
            ))
            scripts = await stack.enter_async_context(httpx.AsyncClient(
                base_url="https://imsdb.com", timeout=40, follow_redirects=False, trust_env=False,
            ))
            app.state.questions = MovieQuestionService(wiki, ollama)
            corpus=None
            provider=os.getenv('PLOTSPOT_MOVIE_WEB_SEARCH','off')
            if provider not in ('off','duckduckgo','startpage','auto'):raise ValueError('Configure off, duckduckgo, startpage or auto search')
            async def movie_identity(movie_id):
                from .movie_web_sources import MovieIdentity
                movie=await load_movie_details(movie_id,store=app.state.catalog_store,provider=app.state.tmdb)
                return MovieIdentity.from_movie(movie)
            if settings.data_source=='tmdb' and provider!='off':
                from .movie_source_corpus import MovieSourceCorpus
                from .web_search import FreeMovieSearch
                corpus=MovieSourceCorpus(FreeMovieSearch(provider),script_client=scripts,reference_client=wiki)
                app.state.questions.corpus=corpus
                app.state.questions.identity_loader=movie_identity
            app.state.source_corpus=corpus
            app.state.questions.story = StoryRag(scripts)
            app.state.preparation = ResearchPreparationJobs(wiki, ollama, app.state.questions.slot,
                corpus=corpus,identity_loader=movie_identity,require_diverse_sources=True)
            if settings.lab_enabled:
                app.state.lab = LabService(
                    FilePath(__file__).resolve().parents[3],
                    LabRunReader(
                        app.state.preparation.store.path,
                        app.state.questions.story.trace_root,
                        MOVIE_ARTICLES.get,
                    ),
                )
            if settings.data_source == "tmdb":
                try:
                    prepared = await asyncio.to_thread(app.state.unified_discovery.index.get)
                    await asyncio.to_thread(prepared.suggestions.suggest, '')
                    for movie in prepared.movies:
                        get_suggestion_index().remember(movie)
                except (OSError, ValueError):
                    pass  # Availability is handled by the search endpoint.
            try:
                await app.state.preparation.open()
                yield
            finally:
                await app.state.preparation.close()
                if corpus is not None:await corpus.close()
                await app.state.unified_discovery.close()


app = FastAPI(title="Movie Companion", version="0.2.0", lifespan=lifespan)
app.include_router(preparation_router)
app.include_router(account_router)
app.include_router(history_router)
app.include_router(community_router)
app.include_router(lab_router)
app.add_middleware(AccountBoundary)

@app.exception_handler(AccountError)
async def account_error(request: Request,error: AccountError):
    headers={'Retry-After':str(error.retry_after)} if error.status==429 else None
    return JSONResponse({'detail':str(error)},status_code=error.status,headers=headers)

@app.exception_handler(RequestValidationError)
async def validation_error(request: Request,error: RequestValidationError):
    if member_path(request.url.path):
        # FastAPI's default validation response can echo a submitted password.
        message=('Check your verification link.' if request.url.path.endswith('/verify-email')
                 else 'Check your username, email and password.' if request.url.path.startswith('/api/auth/')
                 else 'Check the submitted history details.' if request.url.path.startswith('/api/me/history')
                 else 'Check your preference settings.' if request.url.path == '/api/me/preferences'
                 else 'Check your collection names and saved films.' if request.url.path.startswith('/api/me/')
                 else 'Check the submitted movie content and try again.')
        return JSONResponse({'detail':message},status_code=422)
    return await request_validation_exception_handler(request,error)



class QuizRequest(BaseModel):
    allow_spoilers: StrictBool = False



def get_provider(request: Request) -> TmdbClient | None:
    settings = get_settings()
    if settings.data_source == "demo":
        return None
    if not settings.tmdb_read_token:
        raise ProviderError(503, "TMDB mode requires TMDB_READ_TOKEN in backend configuration")
    provider = getattr(request.app.state, "tmdb", None)
    if provider is None:
        raise ProviderError(503, "Movie provider is not ready")
    return provider


def get_catalog_store(request: Request) -> CatalogStore | None:
    return getattr(request.app.state, "catalog_store", None)


def get_catalog_index(request: Request, store):
    service = getattr(request.app.state, 'unified_discovery', None)
    if service is not None and service.store is store:
        return service.index
    index = getattr(request.app.state, 'catalog_index', None)
    if index is None or index.store is not store:
        index = SavedCatalogIndex(store)
        request.app.state.catalog_index = index
    return index


def get_detail_provider(request: Request) -> TmdbClient | None:
    # A saved movie must remain readable even without provider credentials.
    settings = get_settings()
    if settings.data_source == "demo" or not settings.tmdb_read_token:
        return None
    return getattr(request.app.state, "tmdb", None)


def get_question_service(request: Request) -> MovieQuestionService:
    service = getattr(request.app.state, "questions", None)
    if service is None:
        raise HTTPException(503, "Movie questions are not ready yet.")
    return service


def get_content_store() -> ContentStore:
    return ContentStore()


def get_extras_store() -> MovieExtrasStore:
    try:
        return MovieExtrasStore()
    except (OSError, sqlite3.Error):
        raise ProviderError(503, "Saved movie extras are unavailable") from None


@app.get("/api/watch-regions", response_model=WatchRegions)
async def available_watch_regions(store: Annotated[MovieExtrasStore, Depends(get_extras_store)],
                                  provider: Annotated[TmdbClient | None, Depends(get_detail_provider)]):
    return await load_extra('regions',WatchRegions,store=store,provider=provider,
        fetch=lambda client:client.watch_regions(),ttl=timedelta(days=7),stale_for=timedelta(days=30))


@app.get("/api/movies/{movie_id}/watch", response_model=WatchOptions)
async def movie_watch_options(movie_id: Annotated[int, Path(gt=0)],
                              country: Annotated[str, Query(pattern=r'^[A-Z]{2}$')],
                              store: Annotated[MovieExtrasStore, Depends(get_extras_store)],
                              provider: Annotated[TmdbClient | None, Depends(get_detail_provider)]):
    return await load_extra(f'watch:{movie_id}:{country}',WatchOptions,store=store,provider=provider,
        fetch=lambda client:client.watch_options(movie_id,country),ttl=timedelta(hours=6),stale_for=timedelta(days=3),
        matches=lambda value:value.movie_id==movie_id and value.country==country)


@app.get("/api/movies/{movie_id}/related", response_model=RelatedMovies)
async def movie_related(movie_id: Annotated[int, Path(gt=0)],
                        store: Annotated[MovieExtrasStore, Depends(get_extras_store)],
                        provider: Annotated[TmdbClient | None, Depends(get_detail_provider)]):
    return await load_extra(f'related:{movie_id}',RelatedMovies,store=store,provider=provider,
        fetch=lambda client:client.related_movies(movie_id),ttl=timedelta(days=1),stale_for=timedelta(days=7),
        matches=lambda value:value.movie_id==movie_id)


@app.get("/api/movies/{movie_id}/features", response_model=MovieFeatures, dependencies=[Depends(require_user)])
def feature_inventory(movie_id: Annotated[int, Path(gt=0)], store: Annotated[ContentStore, Depends(get_content_store)]):
    try:
        return movie_features(movie_id, store)
    except (ValueError, OSError, sqlite3.Error) as error:
        raise HTTPException(503, "Feature availability could not be checked. Please try again.") from error


def read_collection(store, movie_id, allow_spoilers, kind):
    model = MovieQuiz if kind == "quiz" else MovieFacts
    if not allow_spoilers:
        return model(status="spoiler_permission_required", message="Allow spoilers above to view saved movie content.")
    try:
        saved = store.load(movie_id)
    except (ValueError, OSError) as error:
        raise HTTPException(503, "Saved movie content could not be read.") from error
    if saved is None:
        return model(status="source_unavailable", message="A collection has not been prepared for this movie yet.")
    metadata = {"prepared_at": saved["prepared_at"], "content_version": saved["version"]}
    if kind == "quiz":
        metadata["can_generate_more"] = can_expand_quiz(movie_id, saved[kind])
    return saved[kind].model_copy(update=metadata)


@app.get("/api/movies/{movie_id}/facts", response_model=MovieFacts, dependencies=[Depends(require_user)])
def movie_facts(movie_id: Annotated[int, Path(gt=0)], store: Annotated[ContentStore, Depends(get_content_store)], allow_spoilers: bool = False):
    return read_collection(store, movie_id, allow_spoilers, "facts")


@app.get("/api/movies/{movie_id}/quiz", response_model=MovieQuiz, dependencies=[Depends(require_user)])
def movie_quiz(movie_id: Annotated[int, Path(gt=0)], store: Annotated[ContentStore, Depends(get_content_store)], allow_spoilers: bool = False):
    return read_collection(store, movie_id, allow_spoilers, "quiz")


# Older clients can still POST; these are reads and never prepare content.
@app.post("/api/movies/{movie_id}/facts", response_model=MovieFacts, dependencies=[Depends(require_user)])
def movie_facts_compat(movie_id: Annotated[int, Path(gt=0)], body: QuizRequest, store: Annotated[ContentStore, Depends(get_content_store)]):
    return read_collection(store, movie_id, body.allow_spoilers, "facts")


@app.post("/api/movies/{movie_id}/quiz", response_model=MovieQuiz, dependencies=[Depends(require_user)])
def movie_quiz_compat(movie_id: Annotated[int, Path(gt=0)], body: QuizRequest, store: Annotated[ContentStore, Depends(get_content_store)]):
    return read_collection(store, movie_id, body.allow_spoilers, "quiz")


@app.post("/api/movies/{movie_id}/quiz/more", response_model=MovieQuiz, dependencies=[Depends(require_user), Depends(csrf_check)])
async def more_quiz(movie_id: Annotated[int, Path(gt=0)], body: QuizRequest, store: Annotated[ContentStore, Depends(get_content_store)], service: Annotated[MovieQuestionService, Depends(get_question_service)]):
    try:
        async with asyncio.timeout(180):
            return await generate_more(service, store, movie_id=movie_id, allow_spoilers=body.allow_spoilers)
    except QuestionError as error:
        raise HTTPException(error.status, error.message) from error
    except TimeoutError as error:
        raise HTTPException(504, "Generation took too long. Your saved quiz is unchanged.") from error
    except httpx.HTTPError as error:
        raise HTTPException(503, "Local AI is unavailable. Start Ollama and try again.") from error
    except ValueError as error:
        raise HTTPException(502, "New questions could not be verified. Your saved quiz is unchanged.") from error


@app.post("/api/movies/{movie_id}/questions", response_model=MovieAnswer, dependencies=[Depends(require_user), Depends(csrf_check)])
async def movie_question(
    movie_id: Annotated[int, Path(gt=0)], body: MovieQuestion,
    service: Annotated[MovieQuestionService, Depends(get_question_service)],
) -> MovieAnswer:
    try:
        return await service.ask(movie_id, body)
    except QuestionError as error:
        raise HTTPException(error.status, error.message) from error


@app.exception_handler(sqlite3.Error)
async def private_database_error(request: Request,error: sqlite3.Error):
    return JSONResponse({'detail':'Saved data is temporarily unavailable. Please retry.'},status_code=503)

@app.exception_handler(ProviderError)
async def provider_error(_request: Request, error: ProviderError):
    return JSONResponse(status_code=error.status, content={"detail": error.message})


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "data_source": get_settings().data_source}


@app.get("/api/search/local", response_model=MovieSearchResponse)
@app.get("/api/search/catalog", response_model=MovieSearchResponse)
async def unified_search(
    request: Request,
    q: Annotated[str, Query(max_length=300)] = "",
    genre: Annotated[str | None, Query(max_length=40)] = None,
    max_runtime: Annotated[int | None, Query(ge=1, le=600)] = None,
    language: Annotated[str | None, Query(max_length=40)] = None,
    min_rating: Annotated[float | None, Query(ge=0, le=10, allow_inf_nan=False)] = None,
    preferences: Annotated[AccountPreferences, Depends(discovery_preferences)] = None,
    include_adult: bool = True,
    sort_by: Literal['trusted', 'rating'] = 'trusted',
    page: Annotated[int, Query(ge=1, le=10000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=40)] = 20,
    search_token: Annotated[str | None, Query(pattern=r'^[a-f0-9]{32}$')] = None,
    person_id: Annotated[int | None, Query(gt=0)] = None,
    role: Literal['actor', 'director'] | None = None,
    phase: Literal['local', 'complete'] = 'complete',
) -> MovieSearchResponse:
    try:
        if request.url.path == '/api/search/local':
            phase = 'local'
        body = CatalogQuery(include_adult=include_adult and preferences.include_adult, query=q, genre=genre, language=language, max_runtime=max_runtime, min_rating=min_rating, sort_by=sort_by, page=page, page_size=page_size)
        demo = get_settings().data_source == "demo"
        store = get_catalog_store(request)
        if demo:
            movies = list(load_catalog())
        elif store is not None:
            index = get_catalog_index(request, store)
            if q.strip() and len(q.strip()) <= 120:
                service = getattr(request.app.state, 'unified_discovery', None)
                if service is None or service.store is not store:
                    service = UnifiedDiscovery(get_detail_provider(request), store, index=index)
                    request.app.state.unified_discovery = service
                if phase == 'local':
                    if page != 1 or search_token is not None:
                        raise HTTPException(400, "Local previews are only available before completed pagination")
                    return await service.local_preview(body, person_id=person_id, role=role)
                return await service.search(body, token=search_token, person_id=person_id, role=role)
            movies = await asyncio.to_thread(index.get)
        else:
            raise HTTPException(503, "Saved movie metadata is unavailable.")
        return await asyncio.to_thread(search_catalog, movies, body, demo=demo)
    except (sqlite3.Error, OSError, ValueError):
        raise HTTPException(503, "Saved movie metadata is unavailable.") from None


@app.get("/api/search/names", response_model=NameSearchResult)
async def external_name_search(
    q: Annotated[str, Query(min_length=1, max_length=120)],
    provider: Annotated[TmdbClient | None, Depends(get_provider)],
    store: Annotated[CatalogStore | None, Depends(get_catalog_store)],
    preferences: Annotated[AccountPreferences, Depends(discovery_preferences)],
    include_adult: bool = True,
    page: Annotated[int, Query(ge=1, le=100)] = 1,
    person_id: Annotated[int | None, Query(gt=0)] = None,
    role: Literal['actor', 'director'] = 'actor',
    genre: Annotated[str | None, Query(max_length=40)] = None,
    language: Annotated[str | None, Query(max_length=40)] = None,
    max_runtime: Annotated[int | None, Query(ge=1, le=600)] = None,
) -> NameSearchResult:
    if provider is None or store is None:
        raise ProviderError(503, "Name discovery is unavailable right now.")
    return await search_names(provider, store, NameSearchRequest(include_adult=include_adult and preferences.include_adult, query=q, page=page, person_id=person_id,
                              role=role, genre=genre, language=language, max_runtime=max_runtime))


@app.get("/api/search", response_model=MovieSearchResponse)
async def search(
    preferences: Annotated[AccountPreferences, Depends(discovery_preferences)],
    include_adult: bool = True,
    q: Annotated[str, Query(max_length=120)] = "",
    genre: Annotated[str | None, Query(max_length=40)] = None,
    max_runtime: Annotated[int | None, Query(ge=1, le=600)] = None,
    language: Annotated[str | None, Query(max_length=40)] = None,
    provider: Annotated[TmdbClient | None, Depends(get_provider)] = None,
) -> MovieSearchResponse:
    if provider is not None:
        result = await provider.search(q, genre, max_runtime, language)
        if not (include_adult and preferences.include_adult):
            items = [m for m in result.items if m.adult is not True]
            return result.model_copy(update={'items':items,'total':len(items)})
        return result
    movies = search_movies(q, genre=genre, max_runtime=max_runtime, language=language)
    movies = [m for m in movies if include_adult and preferences.include_adult or m.adult is not True]
    return MovieSearchResponse(items=movies, total=len(movies))


@app.get("/api/movies/{movie_id}", response_model=Movie)
async def movie_detail(movie_id: Annotated[int, Path(gt=0)],
                       provider: Annotated[TmdbClient | None, Depends(get_detail_provider)] = None,
                       store: Annotated[CatalogStore | None, Depends(get_catalog_store)] = None) -> Movie:
    if provider is not None or store is not None or get_settings().data_source == "tmdb":
        return await load_movie_details(movie_id, store=store, provider=provider)
    movie = get_movie(movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie is not in the demo collection")
    return movie


@app.get("/api/search/suggestions", response_model=SuggestionResponse)
async def search_suggestions(
    request: Request,
    q: Annotated[str, Query(max_length=120)] = "",
    include_adult: bool = True,
    preferences: Annotated[AccountPreferences, Depends(discovery_preferences)] = None,
    index: Annotated[SuggestionIndex, Depends(get_suggestion_index)] = None,
    store: Annotated[CatalogStore | None, Depends(get_catalog_store)] = None,
) -> SuggestionResponse:
    try:
        if get_settings().data_source == 'demo':
            if not (include_adult and preferences.include_adult):
                index = SuggestionIndex([m for m in load_catalog() if m.adult is not True])
            return await asyncio.to_thread(index.suggest,q)
        if store is None:
            raise HTTPException(503, 'Search suggestions are temporarily unavailable')
        prepared = await asyncio.to_thread(get_catalog_index(request, store).get)
        filtered = await asyncio.to_thread(prepared.filtered, include_adult and preferences.include_adult)
        return await asyncio.to_thread(filtered.suggestions.suggest,q)
    except (sqlite3.Error, OSError, ValueError):
        raise HTTPException(503, 'Search suggestions are temporarily unavailable') from None


@app.post("/api/discover", deprecated=True)
async def retired_semantic_discovery():
    raise HTTPException(410, "Meaning-based search has been retired. Use /api/search/catalog for keyword search.")
