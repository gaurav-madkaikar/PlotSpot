import { MovieRatingBadge } from './movie-rating-badge'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useLocation } from 'react-router'
import { Film } from 'lucide-react'
import { getRelatedMovies } from '../lib/api'
import type { RelatedMovie } from '../lib/contracts'
import { Button } from './ui/button'

function RelatedTile({ movie }: { movie: RelatedMovie }) {
  const [failed, setFailed] = useState(false)
  const location = useLocation()
  return (
    <Link
      className="related-tile"
      to={`/movies/${movie.id}`}
      state={{ returnTo: location.pathname + location.hash }}
      aria-label={`Explore ${movie.title}`}
    >
      <div className="related-art">
        {movie.poster_url && !failed ? (
          <img
            src={movie.poster_url}
            alt={`${movie.title} poster`}
            width="400"
            height="600"
            loading="lazy"
            onError={() => setFailed(true)}
          />
        ) : (
          <div className="related-placeholder">
            <Film size={28} aria-hidden="true" />
            <span>Poster unavailable</span>
          </div>
        )}
      </div>
      <h3>{movie.title}</h3>
      <div className="related-tile-meta">
        <p>{movie.year ?? 'Year unavailable'}</p>
        <MovieRatingBadge movie={movie} />
      </div>
    </Link>
  )
}
export function MovieRelated({ movieId }: { movieId: number }) {
  const related = useQuery({
    queryKey: ['related-movies', movieId],
    queryFn: async ({ signal }) => {
      const result = await getRelatedMovies(movieId, signal)
      if (result.movie_id !== movieId)
        throw new Error('Mismatched related movies')
      return result
    },
    staleTime: 3600000,
    retry: 1,
  })
  return (
    <section
      className="question-panel related-movies"
      aria-labelledby="related-title"
    >
      <header className="feature-heading">
        <div>
          <p className="eyebrow">KEEP EXPLORING</p>
          <h2 id="related-title">More like this</h2>
        </div>
      </header>
      {related.isPending && <p role="status">Finding related films…</p>}
      {related.isError && (
        <div>
          <p role="status">Related films are unavailable right now.</p>
          <Button variant="outline" onClick={() => void related.refetch()}>
            Retry related films
          </Button>
        </div>
      )}
      {related.data && (
        <>
          {related.data.stale && (
            <p className="watch-note" role="status">
              Showing previously checked recommendations.
            </p>
          )}
          {related.data.items.length ? (
            <div className="related-grid">
              {related.data.items.map((movie) => (
                <RelatedTile key={movie.id} movie={movie} />
              ))}
            </div>
          ) : (
            <p>No related films are listed yet.</p>
          )}
        </>
      )}
    </section>
  )
}
