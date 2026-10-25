import { useState } from 'react'
import { Film } from 'lucide-react'
import type { Movie } from '../lib/contracts'

export function MovieArtwork({
  movie,
  lazy = false,
}: {
  movie: Movie
  lazy?: boolean
}) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null)
  if (!movie.cover_url || failedUrl === movie.cover_url) {
    return (
      <div
        className="poster-placeholder"
        role="img"
        aria-label={`Poster unavailable for ${movie.title}`}
      >
        <Film size={36} aria-hidden="true" />
        <span>Poster unavailable</span>
      </div>
    )
  }
  return (
    <img
      src={movie.cover_url}
      alt={`${movie.artwork_kind === 'poster' ? 'Movie poster' : 'Illustrated cover'} for ${movie.title}`}
      width="400"
      height="600"
      loading={lazy ? 'lazy' : 'eager'}
      onError={() => setFailedUrl(movie.cover_url)}
    />
  )
}
