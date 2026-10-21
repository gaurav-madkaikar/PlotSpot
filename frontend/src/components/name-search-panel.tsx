import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router'
import { searchNames } from '../lib/api'
import { MovieCard } from './movie-card'
import { Button } from './ui/button'
import { LoadingGrid } from './status-panel'

type Props = { query: string; genre: string; language: string; runtime: string }

export function NameSearchPanel({ query, genre, language, runtime }: Props) {
  const [params, setParams] = useSearchParams()
  const open = params.get('lookup') === 'names'
  const rawPage = Number(params.get('name_page') ?? 1)
  const page =
    Number.isInteger(rawPage) && rawPage >= 1 && rawPage <= 100 ? rawPage : 1
  const role = params.get('role') === 'director' ? 'director' : 'actor'
  const person = params.get('person_id')
  const request = new URLSearchParams({ q: query, page: String(page), role })
  if (person && /^[1-9][0-9]*$/.test(person)) request.set('person_id', person)
  if (genre) request.set('genre', genre)
  if (language) request.set('language', language)
  if (runtime) request.set('max_runtime', runtime)
  const key = request.toString()
  const results = useQuery({
    queryKey: ['name-search', key],
    queryFn: ({ signal }) => searchNames(new URLSearchParams(key), signal),
    enabled: open,
    retry: false,
    staleTime: 300_000,
  })
  function navigate(values: Record<string, string | null>) {
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        for (const [key, value] of Object.entries(values)) {
          if (value === null) next.delete(key)
          else next.set(key, value)
        }
        return next
      },
      { preventScrollReset: true },
    )
  }
  if (!open) return null
  const data = results.data
  return (
    <section
      className="name-search-panel"
      aria-label="Title and person results"
      aria-busy={results.isFetching}
    >
      <div className="name-search-heading">
        <div>
          <p className="field-label">Title and person results</p>
          <h3>{data?.selected_person?.name ?? `Matches for “${query}”`}</h3>
        </div>
        <Button
          variant="outline"
          onClick={() =>
            navigate({
              lookup: null,
              person_id: null,
              role: null,
              name_page: null,
            })
          }
        >
          Close
        </Button>
      </div>
      {person && (
        <div className="name-role-controls" aria-label="Filmography role">
          <Button
            variant={role === 'actor' ? 'default' : 'outline'}
            aria-pressed={role === 'actor'}
            onClick={() => navigate({ role: 'actor', name_page: null })}
          >
            Acting
          </Button>
          <Button
            variant={role === 'director' ? 'default' : 'outline'}
            aria-pressed={role === 'director'}
            onClick={() => navigate({ role: 'director', name_page: null })}
          >
            Directed
          </Button>
          <button
            className="text-button"
            onClick={() =>
              navigate({ person_id: null, role: null, name_page: null })
            }
          >
            Choose another person
          </button>
        </div>
      )}
      {results.isPending ? (
        <LoadingGrid />
      ) : results.isError ? (
        <div className="name-search-notice" role="alert">
          <p>
            Name search is unavailable. Your collection results are still below.
          </p>
          <Button variant="outline" onClick={() => void results.refetch()}>
            Try again
          </Button>
        </div>
      ) : (
        data && (
          <>
            {data.people.length > 0 && (
              <div className="person-choices">
                <p className="meaning-help">
                  Choose a person to explore their films.
                </p>
                <div className="person-choice-grid">
                  {data.people.map((person) => (
                    <button
                      key={person.id}
                      className="person-choice"
                      onClick={() =>
                        navigate({
                          person_id: String(person.id),
                          role:
                            person.known_for_department === 'Directing'
                              ? 'director'
                              : 'actor',
                          name_page: null,
                        })
                      }
                    >
                      <strong>{person.name}</strong>
                      <span>
                        {person.known_for_department ?? 'Film professional'}
                      </span>
                      {person.known_for_titles.length > 0 ? (
                        <small>{person.known_for_titles.join(', ')}</small>
                      ) : (
                        <small>Profile {person.id}</small>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}
            <p className="meaning-help" role="status">
              {data.items.length} {data.items.length === 1 ? 'film' : 'films'}{' '}
              on this page
            </p>
            {data.partial && (
              <p className="name-search-notice" role="status">
                Some matches couldn’t be loaded. Try again to refresh this page.{' '}
                <button
                  className="text-button"
                  onClick={() => void results.refetch()}
                >
                  Retry
                </button>
              </p>
            )}
            {data.limited && (
              <p className="meaning-help">
                For more matches, try a more specific name.
              </p>
            )}
            {data.items.length > 0 ? (
              <div className="movie-grid">
                {data.items.map((movie) => (
                  <MovieCard key={movie.id} movie={movie} />
                ))}
              </div>
            ) : (
              <p className="name-search-notice">
                No films match on this page.{' '}
                {data.has_more
                  ? 'Try the next page or adjust your filters.'
                  : 'Try another name or adjust your filters.'}
              </p>
            )}
            {(page > 1 || data.has_more) && (
              <nav className="movie-pagination" aria-label="Name result pages">
                <Button
                  variant="outline"
                  disabled={page <= 1 || results.isFetching}
                  onClick={() => navigate({ name_page: String(page - 1) })}
                >
                  Previous
                </Button>
                <span>Page {page}</span>
                <Button
                  variant="outline"
                  disabled={!data.has_more || results.isFetching}
                  onClick={() => navigate({ name_page: String(page + 1) })}
                >
                  Next
                </Button>
              </nav>
            )}
          </>
        )
      )}
      <p className="name-local-divider">Collection results</p>
    </section>
  )
}
