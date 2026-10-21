import { useAuth } from '../lib/auth'
import { useCallback, useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router'
import { LoaderCircle, Search, X } from 'lucide-react'
import { getSuggestions, searchMovies, searchSavedMovies } from '../lib/api'
import {
  searchSuggestionOptions,
  type SearchOption,
} from '../lib/search-suggestion-options'
import { MovieCard } from './movie-card'
import { ErrorPanel, LoadingGrid } from './status-panel'
import { Button } from './ui/button'

const genres = [
  'Action',
  'Adventure',
  'Animation',
  'Comedy',
  'Crime',
  'Documentary',
  'Drama',
  'Family',
  'Fantasy',
  'History',
  'Horror',
  'Music',
  'Mystery',
  'Romance',
  'Science Fiction',
  'Thriller',
  'TV Movie',
  'War',
  'Western',
]
const languages = [
  '',
  'English',
  'Korean',
  'Japanese',
  'French',
  'Spanish',
  'Italian',
  'German',
  'Hindi',
]
const examples = ['Interstellar', 'Amy Adams', 'Christopher Nolan', 'linguist']

export function MovieSearch() {
  const auth = useAuth()
  const includeAdult = auth.user?.preferences.include_adult ?? true
  const ready = auth.status === 'guest' || auth.status === 'authenticated'

  const [params, setParams] = useSearchParams()
  const query = params.get('q') ?? ''
  const genre = params.get('genre') ?? ''
  const language = params.get('language') ?? ''
  const runtime = params.get('max_runtime') ?? ''
  const rating = params.get('min_rating') ?? ''
  const sortBy = params.get('sort_by') === 'rating' ? 'rating' : 'trusted'
  const rawPage = Number(params.get('page') ?? 1)
  const page =
    Number.isInteger(rawPage) && rawPage >= 1 && rawPage <= 10000 ? rawPage : 1
  const [draft, setDraft] = useState(query)
  const [previousQuery, setPreviousQuery] = useState(query)
  const [composing, setComposing] = useState(false)
  const [dismissedQuery, setDismissedQuery] = useState<string | null>(null)
  // Synchronize navigation during render so a delayed effect cannot erase typing.
  if (previousQuery !== query) {
    setPreviousQuery(query)
    setDismissedQuery(null)
    // A debounce trims the request, not the text the user is still typing.
    if (draft.trim() !== query) setDraft(query)
  }
  useEffect(() => {
    if (params.has('mode'))
      setParams(
        (current) => {
          const next = new URLSearchParams(current)
          next.delete('mode')
          return next
        },
        { replace: true, preventScrollReset: true },
      )
  }, [params, setParams])
  const requestParams = new URLSearchParams({
    unified: 'true',
    page: String(page),
    page_size: '20',
    sort_by: sortBy,
  })
  if (!includeAdult) requestParams.set('include_adult', 'false')
  if (query) requestParams.set('q', query)
  if (genre) requestParams.set('genre', genre)
  if (language) requestParams.set('language', language)
  if (runtime) requestParams.set('max_runtime', runtime)
  if (rating) requestParams.set('min_rating', rating)
  for (const field of ['person_id', 'role', 'search_token']) {
    const value = params.get(field)
    if (value) requestParams.set(field, value)
  }
  const key = requestParams.toString()
  const results = useQuery({
    queryKey: auth.user
      ? ['keyword-movies', key, auth.user.id]
      : ['keyword-movies', key],
    queryFn: ({ signal }) => searchMovies(new URLSearchParams(key), signal),
    enabled: ready,
    retry: false,
    staleTime: 300_000,
  })
  const canPreview =
    Boolean(query.trim()) &&
    page === 1 &&
    !params.has('search_token') &&
    !params.has('person_id') &&
    !params.has('role')
  const preview = useQuery({
    queryKey: auth.user
      ? ['saved-movies', key, auth.user.id]
      : ['saved-movies', key],
    queryFn: ({ signal }) =>
      searchSavedMovies(new URLSearchParams(key), signal),
    enabled: ready && canPreview && !results.data,
    retry: false,
    staleTime: 60_000,
  })
  const suggestions = useQuery({
    queryKey: ['suggestions', query, includeAdult],
    queryFn: ({ signal }) => getSuggestions(query, signal, includeAdult),
    enabled: ready && query.trim().length >= 4 && query.length <= 120,
    retry: false,
  })
  const update = useCallback(
    (key: string, value: string, replace = false) => {
      setParams(
        (current) => {
          const next = new URLSearchParams(current)
          next.delete('mode')
          if (key !== 'page') {
            next.delete('page')
            next.delete('name_page')
            next.delete('search_token')
          }
          if (key === 'q') {
            next.delete('lookup')
            next.delete('person_id')
            next.delete('role')
          }
          if (value) next.set(key, value)
          else next.delete(key)
          return next
        },
        { replace, preventScrollReset: true },
      )
    },
    [setParams],
  )
  useEffect(() => {
    const value = draft.trim()
    if (composing || value === query) return
    const timer = window.setTimeout(() => update('q', value, true), 350)
    return () => window.clearTimeout(timer)
  }, [draft, query, composing, update])
  function changePage(next: number) {
    setParams(
      (current) => {
        const values = new URLSearchParams(current)
        values.set('page', String(next))
        if (results.data?.search_token)
          values.set('search_token', results.data.search_token)
        return values
      },
      { preventScrollReset: true },
    )
    document
      .getElementById('collection-title')
      ?.scrollIntoView({ block: 'start', behavior: 'instant' })
  }
  const savedResults =
    canPreview && preview.data?.items.length ? preview.data : undefined
  const data = ready ? (results.data ?? savedResults) : undefined
  const pending =
    auth.status === 'checking' || (ready && results.isPending && !savedResults)
  const failed = auth.status === 'error' || (results.isError && !savedResults)
  useEffect(() => {
    if (!data?.snapshot_reset || page === 1) return
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        next.delete('page')
        if (data.search_token) next.set('search_token', data.search_token)
        return next
      },
      { replace: true, preventScrollReset: true },
    )
  }, [data, page, setParams])
  const options = searchSuggestionOptions(
    query,
    ready ? (suggestions.data?.items ?? []) : [],
    data?.people ?? [],
    data?.items.map((movie) => movie.title) ?? [],
  )
  function selectSuggestion(item: SearchOption) {
    setDraft(item.label)
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        for (const field of [
          'lookup',
          'name_page',
          'page',
          'search_token',
          'person_id',
          'role',
        ])
          next.delete(field)
        next.set('q', item.label)
        if (item.personId) {
          next.set('person_id', String(item.personId))
          next.set('role', item.kind)
        }
        return next
      },
      { preventScrollReset: true },
    )
  }
  // Cached responses can predate additive API fields during a hot update.
  const appliedGenres = data?.applied_genres ?? []
  return (
    <div className="unified-search">
      <form
        onSubmit={(event) => {
          event.preventDefault()
          if (draft.trim() === query && page === 1 && results.isError)
            void results.refetch()
          else if (!composing) update('q', draft.trim(), true)
        }}
      >
        <div className="discovery-toolbar">
          <div className="search-group">
            <label className="field-label" htmlFor="movie-search">
              Find your next film
            </label>
            <div className="meaning-input-row">
              <div className="search-field">
                <input
                  id="movie-search"
                  type="search"
                  value={draft}
                  maxLength={300}
                  onChange={(event) => setDraft(event.target.value)}
                  onCompositionStart={() => setComposing(true)}
                  onCompositionEnd={() => setComposing(false)}
                  placeholder="Search..."
                  aria-describedby="search-help"
                />
                <button
                  className="search-submit"
                  type="submit"
                  aria-label="Search"
                  title="Search"
                >
                  {results.isFetching ? (
                    <LoaderCircle
                      className="search-spinner"
                      size={20}
                      aria-hidden="true"
                    />
                  ) : (
                    <Search size={20} aria-hidden="true" />
                  )}
                </button>
              </div>
            </div>
          </div>
          <div className="filter-group">
            <label htmlFor="genre-filter" className="field-label">
              Genre
            </label>
            <div className="filter-field">
              <select
                id="genre-filter"
                value={genre}
                onChange={(e) => update('genre', e.target.value)}
              >
                <option value="">All genres</option>
                {genres.map((g) => (
                  <option key={g}>{g}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="filter-group">
            <label htmlFor="runtime-filter" className="field-label">
              Maximum runtime
            </label>
            <div className="filter-field">
              <select
                id="runtime-filter"
                value={runtime}
                onChange={(e) => update('max_runtime', e.target.value)}
              >
                <option value="">Any length</option>
                <option value="120">Under 2 hours</option>
                <option value="150">Up to 2½ hours</option>
              </select>
            </div>
          </div>
          <div className="filter-group">
            <label htmlFor="language-filter" className="field-label">
              Language
            </label>
            <div className="filter-field">
              <select
                id="language-filter"
                value={language}
                onChange={(e) => update('language', e.target.value)}
              >
                {languages.map((l) => (
                  <option key={l} value={l}>
                    {l || 'All languages'}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="filter-group">
            <label htmlFor="rating-filter" className="field-label">
              Minimum rating
            </label>
            <div className="filter-field">
              <select
                id="rating-filter"
                value={rating}
                onChange={(e) => update('min_rating', e.target.value)}
              >
                <option value="">Any rating</option>
                {[6, 7, 8, 9].map((score) => (
                  <option key={score} value={score}>
                    {score}+ / 10
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
        <p id="search-help" className="meaning-help">
          Search titles, cast, directors or description keywords.
        </p>
      </form>
      <div className="meaning-examples" aria-label="Ideas to try">
        {examples.map((example) => (
          <button
            key={example}
            onClick={() => {
              setDraft(example)
              update('q', example)
            }}
          >
            {example}
          </button>
        ))}
      </div>
      <div className="results-line">
        {(query || genre || runtime || language || rating) && (
          <button
            className="text-button"
            onClick={() =>
              setParams(sortBy === 'rating' ? { sort_by: 'rating' } : {}, {
                preventScrollReset: true,
              })
            }
          >
            <X size={14} aria-hidden="true" />
            Clear filters
          </button>
        )}
        <p role="status">
          {pending
            ? 'Finding your results…'
            : failed
              ? 'Collection unavailable'
              : data
                ? `${data.items.length} ${data.items.length === 1 ? 'result' : 'results'}${query ? ` matching “${query}”` : ''}`
                : ''}
        </p>
        <div className="discovery-sort">
          <label htmlFor="discovery-sort">Sort by</label>
          <select
            id="discovery-sort"
            value={sortBy}
            aria-describedby="sort-help"
            onChange={(event) =>
              update(
                'sort_by',
                event.target.value === 'trusted' ? '' : event.target.value,
              )
            }
          >
            <option value="trusted">Best rated</option>
            <option value="rating">Highest score</option>
          </select>
          <span id="sort-help" className="sr-only">
            Best rated balances movie scores with the number of votes. Highest
            score uses the original TMDB average.
          </span>
        </div>
      </div>
      {savedResults && !results.data && (
        <div className="search-progress" role="status">
          {results.isError ? (
            <Button variant="ghost" onClick={() => void results.refetch()}>
              Retry live search
            </Button>
          ) : (
            <>
              <LoaderCircle
                size={14}
                aria-hidden="true"
                className="search-spinner"
              />
              Finding more films…
            </>
          )}
        </div>
      )}
      {data && appliedGenres.length > 0 && (
        <p className="search-correction">
          Matching {appliedGenres.join(' and ')} films.
        </p>
      )}
      {results.data?.matched_query && (
        <p className="search-correction">
          Showing matches for <strong>{results.data.matched_query}</strong>.
        </p>
      )}
      {!pending &&
        !failed &&
        dismissedQuery !== query &&
        options.length > 0 && (
          <section className="suggestion-panel" aria-label="Search suggestions">
            <div className="suggestion-heading">
              <strong>Did you mean?</strong>
              <Button
                variant="ghost"
                className="suggestion-dismiss"
                aria-label="Dismiss search suggestions"
                onClick={() => setDismissedQuery(query)}
              >
                <X size={18} aria-hidden="true" />
              </Button>
            </div>
            <div className="suggestion-options">
              {options.map((item) => (
                <Button
                  key={item.key}
                  variant="outline"
                  aria-label={`Search for ${item.label} (${item.kind})${item.context ? `, known for ${item.context}` : ''}`}
                  onClick={() => selectSuggestion(item)}
                >
                  {item.label}
                  <span className="suggestion-kind">
                    {item.kind === 'movie'
                      ? 'Movie'
                      : item.kind === 'director'
                        ? 'Director'
                        : 'Actor'}
                  </span>
                  {item.context && (
                    <span className="suggestion-context">{item.context}</span>
                  )}
                </Button>
              ))}
            </div>
          </section>
        )}
      {pending ? (
        <LoadingGrid />
      ) : failed ? (
        <ErrorPanel
          retry={() =>
            void (auth.status === 'error' ? auth.refresh() : results.refetch())
          }
        />
      ) : (
        data &&
        (data.items.length ? (
          <div className="movie-grid">
            {data.items.map((movie) => (
              <MovieCard
                key={movie.id}
                movie={movie}
                primaryGenre={appliedGenres.find((g) =>
                  movie.genres.includes(g),
                )}
              />
            ))}
          </div>
        ) : (
          <div className="status-panel">
            <Search size={28} aria-hidden="true" />
            <h3>
              {data.total > 0
                ? 'This page is unavailable.'
                : data.partial
                  ? 'Search couldn’t be completed.'
                  : 'No films found just yet.'}
            </h3>
            <p>
              {data.total > 0
                ? 'Return to the first page of these results.'
                : data.partial
                  ? 'Please try again shortly.'
                  : 'Try a different title or name, or clear your filters.'}
            </p>
            <Button
              variant="outline"
              onClick={() =>
                data.total > 0
                  ? update('page', '')
                  : data.partial
                    ? void results.refetch()
                    : setParams({}, { preventScrollReset: true })
              }
            >
              {data.total > 0
                ? 'First page'
                : data.partial
                  ? 'Try again'
                  : 'Show all films'}
            </Button>
          </div>
        ))
      )}
      {results.data && data && data.total_pages > 1 && (
        <nav className="movie-pagination" aria-label="Movie pages">
          <Button
            variant="outline"
            disabled={page <= 1 || results.isFetching}
            onClick={() => changePage(page - 1)}
          >
            Previous
          </Button>
          <span>
            Page {data.page} of {data.total_pages}
          </span>
          <Button
            variant="outline"
            disabled={page >= data.total_pages || results.isFetching}
            onClick={() => changePage(page + 1)}
          >
            Next
          </Button>
        </nav>
      )}
    </div>
  )
}
