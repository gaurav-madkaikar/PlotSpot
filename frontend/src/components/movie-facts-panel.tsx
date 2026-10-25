import { useEffect, useRef, useState } from 'react'
import { loadMovieFacts } from '../lib/api'
import type { MovieFacts } from '../lib/contracts'
import { Button } from './ui/button'

export function MovieFactsPanel({
  movieId,
  available,
  allowSpoilers,
}: {
  movieId: number
  available: boolean
  allowSpoilers: boolean
}) {
  const [facts, setFacts] = useState<MovieFacts | null>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const controller = useRef<AbortController | null>(null)
  useEffect(() => {
    if (allowSpoilers && available) void load()
    return () => controller.current?.abort()
  }, [movieId, allowSpoilers, available])
  async function load() {
    if (pending || !allowSpoilers) return
    const active = new AbortController()
    controller.current = active
    setPending(true)
    setError('')
    try {
      const result = await loadMovieFacts(movieId, allowSpoilers, active.signal)
      if (!active.signal.aborted) setFacts(result)
    } catch (problem) {
      if (!active.signal.aborted)
        setError(
          problem instanceof Error ? problem.message : 'Please try again.',
        )
    } finally {
      if (!active.signal.aborted) setPending(false)
    }
  }
  const readingSources =
    facts?.reading_sources.filter((source) => source.kind !== 'early_draft') ??
    []
  const sourceUrls = [
    ...(facts?.items.flatMap((item) =>
      item.citations.map((c) => c.source_ref),
    ) ?? []),
    ...readingSources.map((s) => s.source_ref),
  ]
  const wikipediaUsed = sourceUrls.some(
    (url) => new URL(url).hostname === 'en.wikipedia.org',
  )
  const publishers: Record<string, string> = {
    'en.wikipedia.org': 'Wikipedia',
    'time.com': 'TIME',
    'www.bfi.org.uk': 'BFI',
    'authors.library.caltech.edu': 'CaltechAUTHORS',
  }
  const sourceNames = [
    ...new Set(
      sourceUrls.map((url) => {
        const host = new URL(url).hostname
        return publishers[host] ?? host.replace(/^www\./, '')
      }),
    ),
  ]
  return (
    <section
      className="question-panel facts-panel"
      aria-labelledby="facts-heading"
    >
      <header className="feature-heading">
        <div>
          <p className="eyebrow">BEHIND THE SCENES</p>
          <h2 id="facts-heading">Off-screen stories.</h2>
          <p>The craft, choices, and people behind the film.</p>
        </div>
        <span className="feature-badge">
          {available
            ? `${facts?.items.length || 5} discoveries`
            : 'Not available yet'}
        </span>
      </header>
      {!available ? (
        <p>Facts have not been prepared for this film yet.</p>
      ) : (
        <>
          {!allowSpoilers && (
            <p role="status" className="question-permission">
              Allow spoilers above to explore this collection.
            </p>
          )}
          {!facts && allowSpoilers && (
            <Button
              type="button"
              disabled={!allowSpoilers || pending}
              onClick={() => void load()}
            >
              {pending ? 'Loading saved facts…' : 'Retry loading facts'}
            </Button>
          )}
          {pending && (
            <>
              <p role="status">Loading the saved production collection…</p>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  controller.current?.abort()
                  setPending(false)
                  setError('Facts preparation was cancelled.')
                }}
              >
                Cancel facts
              </Button>
            </>
          )}
          {error && (
            <p role="alert" className="question-error">
              {error}
            </p>
          )}
          <div className="fact-grid">
            {facts?.items.map((item, index) => (
              <article key={item.id} className="fact-card">
                <span className="fact-number">
                  {String(index + 1).padStart(2, '0')}
                </span>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
                <div className="question-citations">
                  {item.citations.map((citation) => (
                    <details key={citation.passage_id}>
                      <summary>Source & context</summary>
                      <p className="source-publisher">
                        {citation.source_label}
                      </p>
                      <blockquote>{citation.excerpt}</blockquote>
                      <a
                        className="text-link"
                        href={citation.source_ref}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        View source{' '}
                      </a>
                    </details>
                  ))}
                </div>
              </article>
            ))}
          </div>
          {!!readingSources.length && (
            <aside
              className="reading-sources"
              aria-labelledby="reading-heading"
            >
              <p className="eyebrow" id="reading-heading">
                MORE TO EXPLORE
              </p>
              <div className="reading-grid">
                {readingSources.map((source) => (
                  <a
                    key={source.source_ref}
                    className="reading-link"
                    href={source.source_ref}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <span className="reading-kind">
                      {
                        {
                          early_draft: 'Screenplay draft',
                          research: 'Research',
                          interview: 'Interview',
                          article: 'Film craft',
                        }[source.kind]
                      }
                      {source.date && ` · ${source.date.slice(0, 4)}`}
                    </span>
                    <span className="reading-title">{source.title}</span>
                    <span className="reading-note">{source.note}</span>
                    <span className="reading-publisher">
                      {source.publisher}
                    </span>
                  </a>
                ))}
              </div>
            </aside>
          )}
          {facts && (
            <p className="feature-credit">
              Production background · {sourceNames.join(', ')}
              {wikipediaUsed && (
                <>
                  {' '}
                  ·{' '}
                  <a
                    href="https://en.wikipedia.org/wiki/Wikipedia:Copyrights"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Wikipedia attribution
                  </a>
                </>
              )}
            </p>
          )}
        </>
      )}
    </section>
  )
}
