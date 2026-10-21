import { MovieRatingBadge } from './movie-rating-badge'
import { ArrowUpRight } from 'lucide-react'
import { Link, useLocation } from 'react-router'
import type { Movie } from '../lib/contracts'
import { SaveMovieControl } from './save-movie-control'
import { MovieArtwork } from './movie-artwork'

export function MovieCard({
  movie,
  primaryGenre,
}: {
  movie: Movie
  primaryGenre?: string
}) {
  const location = useLocation()
  return (
    <article className="movie-card">
      <div className="movie-art">
        <Link
          className="movie-art-link"
          to={`/movies/${movie.id}`}
          state={{ returnTo: location.pathname + location.search }}
          aria-label={`Explore ${movie.title}`}
        >
          <MovieArtwork movie={movie} lazy />
          <span className="art-arrow">
            <ArrowUpRight size={18} aria-hidden="true" />
          </span>
        </Link>
        <SaveMovieControl movieId={movie.id} title={movie.title} compact />
      </div>
      <Link
        className="movie-title-link"
        to={`/movies/${movie.id}`}
        state={{ returnTo: location.pathname + location.search }}
      >
        <h3>{movie.title}</h3>
      </Link>
      <div className="movie-preview-meta">
        <p className="movie-meta">
          {movie.year ?? 'Year unavailable'}
          <span aria-hidden="true">·</span>
          {primaryGenre && movie.genres.includes(primaryGenre)
            ? primaryGenre
            : (movie.genres[0] ?? 'Genre unavailable')}
        </p>
        <MovieRatingBadge movie={movie} />
      </div>
    </article>
  )
}
