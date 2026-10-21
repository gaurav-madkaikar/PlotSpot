export type RatingRecord = {
  vote_average?: number | null
  vote_count?: number | null
  detail_metadata?: {
    vote_average?: number | null
    vote_count?: number | null
  } | null
}
export function movieRating(
  movie: RatingRecord,
): { score: number; votes: number } | null {
  const source = movie.detail_metadata ?? movie
  const score = source.vote_average,
    votes = source.vote_count
  return score != null && votes != null && votes > 0 ? { score, votes } : null
}
