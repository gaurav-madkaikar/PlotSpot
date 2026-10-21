"""One bounded discovery pool, frozen before pagination. No model calls."""
import asyncio
import math
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from time import monotonic
from uuid import uuid4

from .catalog_search import CatalogQuery, eligible, identity_priority, identity_sort_key, query_identity, search_catalog
from .catalog_index import SavedCatalogIndex
from .movie_ratings import RATING_POLICY
from .name_discovery import acting_movie_ids, director_movie_ids
from .schemas import MovieSearchResponse, SearchPerson
from .search_text import normalize_search_text
from .tmdb_client import ProviderError


@dataclass
class Snapshot:
    key: tuple
    expires: float
    response: MovieSearchResponse


class UnifiedDiscovery:
    def __init__(self, provider, store, *, ttl=300, capacity=64, deadline=20, movie_limit=60, index=None):
        self.provider, self.store = provider, store
        self.index = index or SavedCatalogIndex(store)
        self.ttl, self.capacity, self.deadline, self.movie_limit = ttl, capacity, deadline, movie_limit
        self.snapshots: OrderedDict[str, Snapshot] = OrderedDict()
        self.pending: dict[tuple, asyncio.Task] = {}
        self.slots = asyncio.Semaphore(2)

    async def close(self):
        tasks = list(self.pending.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.pending.clear()

    async def local_preview(self, request, *, person_id=None, role=None):
        prepared = await asyncio.to_thread(self.index.get)
        local = await asyncio.to_thread(search_catalog, prepared, request, paginate=False)
        needle, query_role = query_identity(local.matched_query or request.query)
        priorities = [identity_priority(m, needle, query_role, record=prepared.by_id[m.id]) for m in local.items]
        # Person IDs/credits require provider verification. Do not flash another person's films.
        person_query = person_id is not None or role or query_role or (any(p in (1, 3) for p in priorities) and 0 not in priorities)
        items = [] if person_query else local.items
        return local.model_copy(update={'items': items[:request.page_size], 'total': len(items),
                                       'total_pages': 0, 'page': 1})

    async def search(self, request: CatalogQuery, *, token=None, person_id=None, role=None):
        key = (request.query.strip().casefold(), request.genre, request.language, request.max_runtime, request.min_rating, request.sort_by, request.include_adult, RATING_POLICY, person_id, role)
        now = monotonic()
        for old in [t for t, s in self.snapshots.items() if s.expires <= now]:
            del self.snapshots[old]
        snapshot = self.snapshots.get(token) if token else None
        reset = bool(token and (snapshot is None or snapshot.key != key))
        if reset or (snapshot and snapshot.response.partial and request.page == 1):
            snapshot = None
        if snapshot is None:
            # Partial first pages must be retryable; partial tokens still freeze later pages.
            snapshot = next((s for s in reversed(self.snapshots.values())
                             if s.key == key and not s.response.partial), None)
        if snapshot is None:
            task = self.pending.get(key)
            if task is None:
                task = asyncio.create_task(self._build(request, key, person_id, role))
                self.pending[key] = task
                def finished(done):
                    self.pending.pop(key, None)
                    if not done.cancelled():
                        done.exception()  # Observe errors even if every browser request cancelled.
                task.add_done_callback(finished)
            snapshot = await asyncio.shield(task)
        self.snapshots.move_to_end(snapshot.response.search_token)
        page = 1 if reset else request.page
        start = (page - 1) * request.page_size
        return snapshot.response.model_copy(update={
            'items': snapshot.response.items[start:start + request.page_size],
            'page': page, 'page_size': request.page_size,
            'total_pages': math.ceil(snapshot.response.total / request.page_size),
            'snapshot_reset': reset,
        })

    async def _build(self, request, key, person_id, role):
        # Load once: catalog growth during another search cannot reorder this pool.
        prepared = await asyncio.to_thread(self.index.get)
        movies = prepared.movies
        local = await asyncio.to_thread(search_catalog, prepared, request, paginate=False)
        discovered, fresh, people, selected = {}, [], [], None
        partial, limited, person_role = False, False, role
        saved = {m.id: m for m in movies}
        title_candidates = {}
        needle, query_role = query_identity(request.query)
        effective = local.matched_query or needle
        verified_credits = set()

        async def hydrate(mid):
            nonlocal partial
            old = saved.get(mid)
            candidate = title_candidates.get(mid)
            if not request.include_adult and ((candidate and candidate.adult is True) or (old and old.adult is True)):
                return
            # Old lightweight tiles omitted vote fields. Refresh from the title
            # result itself when available, without per-movie detail requests.
            missing_preview_votes = bool(old and old.detail_metadata is None and old.vote_count is None
                                         and candidate is not None and candidate.vote_count is not None)
            if old and not missing_preview_votes and (request.max_runtime is None or old.runtime_minutes is not None) and await asyncio.to_thread(self.store.metadata_is_fresh, mid):
                discovered[mid] = old
                return
            try:
                movie = await self.provider.movie_preview(mid, candidate=title_candidates.get(mid), require_runtime=request.max_runtime is not None)
                if movie.id != mid or movie.source != 'tmdb':
                    raise ProviderError(502, 'Movie identity could not be verified.')
                discovered[mid] = movie
                fresh.append(movie)
            except ProviderError:
                partial = True
                if old:
                    discovered[mid] = old

        async def external():
            nonlocal partial, limited, selected, people, person_role
            if self.provider is None:
                partial = True
                return
            title_page, person_page = await asyncio.gather(
                self.provider.search_movie_names(needle, page=1),
                self.provider.search_person_names(effective, page=1), return_exceptions=True)
            ids = []
            title_query = needle
            if isinstance(title_page, ProviderError):
                partial = True
            elif isinstance(title_page, Exception):
                raise title_page
            else:
                title_candidates.update({m.id: m for m in title_page.items})
                ids = [m.id for m in title_page.items]
                if not ids and local.matched_query:
                    title_query = effective
                    title_page = await self.provider.search_movie_names(effective, page=1)
                    title_candidates.update({m.id: m for m in title_page.items})
                    ids = [m.id for m in title_page.items]
                if title_page.total_pages > 1:
                    try:
                        second = await self.provider.search_movie_names(title_query, page=2)
                        title_candidates.update({m.id: m for m in second.items})
                        ids.extend(m.id for m in second.items)
                        limited |= second.total_pages > 2 or second.limited
                    except ProviderError:
                        partial = True
                limited |= title_page.limited
            if isinstance(person_page, ProviderError):
                partial = True
            elif isinstance(person_page, Exception):
                raise person_page
            else:
                people = person_page.items
                exact = [p for p in people if normalize_search_text(p.name) == normalize_search_text(effective)]
                if len(exact) == 1 and person_id is None and person_page.total_pages <= 1:
                    selected = exact[0]
                limited |= person_page.limited or person_page.total_pages > 1
            if person_id is not None:
                selected = await self.provider.person(person_id)
            if selected:
                person_role = role or query_role or ('director' if selected.known_for_department == 'Directing' else 'actor')
                try:
                    credits = await self.provider.person_movie_credits(selected.id)
                    credit_ids = director_movie_ids(credits['crew']) if person_role == 'director' else acting_movie_ids(credits['cast'])
                    verified_credits.update(credit_ids)
                    # Include saved credits beyond the hydration bound (e.g. a cameo omitted from top cast).
                    discovered.update({mid: saved[mid] for mid in credit_ids if mid in saved})
                    ids = [*credit_ids, *ids]
                except ProviderError:
                    partial = True
                people = []
            else:
                # Clarification is only useful for names, not every weak provider person match.
                candidates = [p for p in people if normalize_search_text(effective) in normalize_search_text(p.name)]
                exact = [p for p in candidates if normalize_search_text(p.name) == normalize_search_text(effective)]
                people = exact or candidates
            ids = list(dict.fromkeys(ids))
            limited |= len(ids) > self.movie_limit
            ids = ids[:self.movie_limit]
            # Child tasks belong to this timeout; cancellation always joins them.
            tasks = [asyncio.create_task(hydrate(mid)) for mid in ids]
            try:
                await asyncio.gather(*tasks)
            finally:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

        try:
            # Reject excess distinct work promptly instead of building an unbounded queue.
            if self.slots.locked():
                partial = True
            else:
                async with self.slots, asyncio.timeout(self.deadline):
                    await external()
        except (TimeoutError, ProviderError):
            partial = True
        if fresh:
            await asyncio.to_thread(self.store.import_movies, fresh, fetched_at=datetime.now(timezone.utc).isoformat(), preview=True)
        if local.matched_query and not query_role and any(identity_priority(m, needle) == 0 for m in discovered.values()):
            # A valid external exact title outranks a guess based on the smaller saved corpus.
            local = await asyncio.to_thread(search_catalog, prepared, request, paginate=False, correct_typos=False)
        if selected:
            # Name strings rank credits, but verified IDs determine membership.
            local = await asyncio.to_thread(search_catalog, prepared, request.model_copy(update={
                'query': f"{'directed by' if person_role == 'director' else 'starring'} {selected.name}"}), paginate=False)
        merged = {m.id: m for m in local.items}
        if selected:
            merged = {mid: m for mid, m in merged.items() if mid in verified_credits}
        for mid, movie in discovered.items():
            if eligible(movie, request) and (not (selected or role or query_role or person_id) or mid in verified_credits):
                merged[mid] = movie
        rank_needle = normalize_search_text(selected.name) if selected else query_identity(local.matched_query or request.query)[0]
        def ranking(movie):
            return identity_sort_key(movie, rank_needle, person_role if selected else query_role,
                                     fallback=1 if movie.id in verified_credits else 4,
                                     record=prepared.by_id.get(movie.id) if movie is saved.get(movie.id) else None,
                                     sort_by=request.sort_by)
        items = sorted(merged.values(), key=ranking)
        response = local.model_copy(update={
            'items': items, 'total': len(items), 'partial': partial, 'limited': limited,
            'people': [SearchPerson.model_validate(p.model_dump()) for p in people],
            'selected_person': SearchPerson.model_validate(selected.model_dump()) if selected else None,
            'person_role': person_role if selected else None, 'search_token': uuid4().hex,
        })
        snapshot = Snapshot(key, monotonic() + self.ttl, response)
        self.snapshots[response.search_token] = snapshot
        while len(self.snapshots) > self.capacity:
            self.snapshots.popitem(last=False)
        return snapshot
