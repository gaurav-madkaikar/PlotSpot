import { Star } from 'lucide-react'
import { movieRating, type RatingRecord } from '../lib/movie-ratings'
export function MovieRatingBadge({ movie }: { movie: RatingRecord }) {
  const rating = movieRating(movie)
  const voteLabel = rating?.votes === 1 ? 'vote' : 'votes'
  const compactVotes = rating
    ? new Intl.NumberFormat('en-US', {
        notation: 'compact',
        maximumFractionDigits: 1,
      }).format(rating.votes)
    : ''
  return rating ? (
    <span
      className="movie-preview-rating"
      aria-label={`TMDB rating ${rating.score.toFixed(1)} out of 10 from ${rating.votes.toLocaleString()} ${voteLabel}`}
      title={`${rating.votes.toLocaleString()} TMDB ${voteLabel}`}
    >
      <Star size={14} aria-hidden="true" />
      <strong>{rating.score.toFixed(1)}</strong>
      <span>TMDB</span>
      <span className="movie-preview-votes" aria-hidden="true">
        {compactVotes} {voteLabel}
      </span>
    </span>
  ) : (
    <span className="movie-preview-unrated">
      {(movie.detail_metadata ?? movie).vote_count === 0
        ? 'Not rated'
        : 'Rating unavailable'}
    </span>
  )
}
