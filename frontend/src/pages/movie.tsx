import { useMovieVisit } from '../lib/use-movie-visit'
import { useState } from 'react'
import { useAuth } from '../lib/auth'
import { MemberFeatureGate } from '../components/member-feature-gate'
import { MovieCommunityPanel } from '../components/movie-community-panel'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router'
import { Clock3, Globe2, Star } from 'lucide-react'
import { MovieCast, MovieDetails } from '../components/movie-overview'
import {
  MovieFeatureSection,
  MovieSectionNavigation,
} from '../components/movie-section-navigation'
import { ApiError, getMovie, getMovieFeatures } from '../lib/api'
import { runtimeLabel } from '../lib/utils'
import { useCollection } from '../lib/collection'
import { SaveMovieControl } from '../components/save-movie-control'
import { Button } from '../components/ui/button'
import { MovieArtwork } from '../components/movie-artwork'
import { MovieTrailer } from '../components/movie-trailer'
import { MovieWatchOptions } from '../components/movie-watch-options'
import { MovieRelated } from '../components/movie-related'
import { MovieQuestionPanel } from '../components/movie-question-panel'
import { MovieQuizPanel } from '../components/movie-quiz-panel'
import { MovieFactsPanel } from '../components/movie-facts-panel'
import {
  ErrorPanel,
  LoadingPage,
  MissingMovie,
} from '../components/status-panel'

export function MoviePage() {
  const auth = useAuth()
  const member = !!auth.user && auth.status === 'authenticated'
  const [pendingSpoiler, setPendingSpoiler] = useState<{
    id: number
    owner: string
    allowed: boolean
  } | null>(null)
  const { movieId } = useParams()
  const id = Number(movieId)
  const validId = Number.isSafeInteger(id) && id > 0
  const movie = useQuery({
    queryKey: ['movie', id],
    queryFn: ({ signal }) => getMovie(id, signal),
    enabled: validId,
    retry: (count, error) =>
      !(error instanceof ApiError && error.status === 404) && count < 1,
  })
  const visit = useMovieVisit(movie.isSuccess ? movie.data : undefined)
  const availability = useQuery({
    queryKey: ['movie-features', auth.user?.id, id],
    queryFn: ({ signal }) => getMovieFeatures(id, signal),
    enabled: validId && member,
    gcTime: 0,
    staleTime: 30_000,
    retry: 1,
  })
  const {
    watched,
    toggleWatched,
    loading: collectionLoading,
    saving: collectionSaving,
    loadError: collectionError,
  } = useCollection()
  if (
    !validId ||
    (movie.error instanceof ApiError && movie.error.status === 404)
  )
    return <MissingMovie />
  if (movie.isPending) return <LoadingPage />
  if (movie.isError) return <ErrorPanel retry={() => void movie.refetch()} />
  const film = movie.data
  const hasWatched =
    member &&
    (pendingSpoiler?.id === id && pendingSpoiler.owner === auth.user?.id
      ? pendingSpoiler.allowed
      : watched.includes(id) ||
        (auth.status === 'authenticated' &&
          auth.user?.preferences.allow_spoilers === true))

  return (
    <div className="page-width detail-page">
      {visit.issue && (
        <div className="visit-history-error">
          <p role="status">{visit.issue}</p>
          <Button variant="ghost" onClick={visit.retry}>
            Retry saving visit
          </Button>
        </div>
      )}
      <section className="movie-hero-section" aria-labelledby="movie-title">
        <div className="movie-detail-hero">
          <div className="detail-cover">
            <MovieArtwork movie={film} />
          </div>
          <div className="detail-copy">
            <p className="eyebrow">
              <span className="section-index">02 /</span>MEDIA CARNIVAL
            </p>
            <h1 id="movie-title">{film.title}</h1>
            {film.tagline && <p className="detail-tagline">{film.tagline}</p>}
            <div className="detail-rating" aria-label="TMDB rating">
              <Star size={19} aria-hidden="true" />
              <strong>
                {film.detail_metadata?.vote_average != null
                  ? film.detail_metadata.vote_average.toFixed(1)
                  : 'Not rated'}
              </strong>
              {film.detail_metadata?.vote_average != null && <span>/ 10</span>}
              <div>
                <span>TMDB rating</span>
                <small>
                  {film.detail_metadata?.vote_count
                    ? `${new Intl.NumberFormat('en-US').format(film.detail_metadata.vote_count)} votes`
                    : 'No votes reported'}
                </small>
              </div>
            </div>
            <div className="detail-meta">
              <span>{film.year ?? 'Year unavailable'}</span>
              <span>
                <Clock3 size={15} aria-hidden="true" />
                {runtimeLabel(film.runtime_minutes)}
              </span>
              <span>
                <Globe2 size={15} aria-hidden="true" />
                {film.language}
              </span>
            </div>
            <div className="genre-tags">
              {film.genres.map((genre) => (
                <span key={genre}>{genre}</span>
              ))}
            </div>
            <p className="detail-overview">
              {film.overview || 'Overview unavailable.'}
            </p>
            <p className="director-credit">
              {film.director ? (
                <>
                  Directed by <strong>{film.director}</strong>
                </>
              ) : (
                'Director unavailable'
              )}
            </p>
            <div className="detail-actions">
              {film.detail_metadata?.trailer && (
                <MovieTrailer
                  key={`${id}-${film.detail_metadata.trailer.youtube_key}`}
                  trailer={film.detail_metadata.trailer}
                  movieTitle={film.title}
                />
              )}
              <SaveMovieControl key={id} movieId={id} title={film.title} />
            </div>
          </div>
        </div>
      </section>
      <MovieSectionNavigation key={`navigation-${id}`} />
      <section
        id="about"
        className="movie-about-section"
        aria-label="About the film"
      >
        <div className="movie-section-stack">
          <MovieCast movie={film} />
          <MovieDetails movie={film} />
          <MovieFeatureSection id="watch" title="Where to watch">
            <MovieWatchOptions movieId={id} />
          </MovieFeatureSection>
        </div>
      </section>
      <div
        className="movie-section-stack"
        key={`sections-${id}-${auth.user?.id ?? 'guest'}-${auth.status === 'error'}`}
      >
        <div className="movie-explore-heading">
          <div>
            <p className="eyebrow">EXPLORE THE FILM</p>
            <h2>Beyond the screen</h2>
          </div>
          {member && (
            <label className="spoiler-control">
              <span>Allow spoilers</span>
              <input
                type="checkbox"
                role="switch"
                aria-label="Allow spoilers"
                aria-describedby="spoiler-help"
                checked={hasWatched}
                disabled={
                  collectionLoading || collectionSaving || collectionError
                }
                onChange={(event) => {
                  const allowed = event.currentTarget.checked
                  setPendingSpoiler({ id, owner: auth.user!.id, allowed })
                  // The visit override also works when the account default is on.
                  // Keep the existing per-film opt-in separate from that default.
                  if (watched.includes(id) !== allowed)
                    void toggleWatched(id).then((saved) => {
                      if (!saved) setPendingSpoiler(null)
                    })
                }}
              />
              <span className="spoiler-track" aria-hidden="true">
                <span />
              </span>
              <span className="spoiler-state" aria-hidden="true">
                {hasWatched ? 'On' : 'Off'}
              </span>
            </label>
          )}
          {member && (
            <p id="spoiler-help">
              {hasWatched
                ? 'Story and ending details are visible.'
                : 'Enable to reveal saved content and explore story details.'}
            </p>
          )}
        </div>
        {member && availability.isPending && (
          <p role="status">Checking available features…</p>
        )}
        {member && availability.isError && (
          <div className="feature-availability-error">
            <p role="alert">Feature availability could not be checked.</p>
            <Button onClick={() => void availability.refetch()}>
              Retry features
            </Button>
          </div>
        )}
        <MovieFeatureSection id="facts" title="Facts">
          <MemberFeatureGate movieId={id} section="facts">
            {availability.data && (
              <MovieFactsPanel
                key={`${id}-${hasWatched}`}
                movieId={id}
                available={availability.data.facts}
                allowSpoilers={hasWatched}
              />
            )}
          </MemberFeatureGate>
        </MovieFeatureSection>
        <MovieFeatureSection id="quiz" title="Quiz">
          <MemberFeatureGate movieId={id} section="quiz">
            {availability.data && (
              <MovieQuizPanel
                key={`${id}-${hasWatched}`}
                movieId={id}
                available={availability.data.quiz}
                allowSpoilers={hasWatched}
              />
            )}
          </MemberFeatureGate>
        </MovieFeatureSection>
        <MovieFeatureSection id="discuss" title="Discuss">
          <MemberFeatureGate movieId={id} section="discuss">
            <MovieCommunityPanel
              key={`community-${id}-${auth.user?.id}-${hasWatched}`}
              movieId={id}
              allowSpoilers={hasWatched}
            />
            {availability.data && (
              <MovieQuestionPanel
                key={`${id}-${hasWatched}`}
                movieId={id}
                movieTitle={film.title}
                available={availability.data.discussion}
                allowSpoilers={hasWatched}
              />
            )}
          </MemberFeatureGate>
        </MovieFeatureSection>
        <MovieFeatureSection id="related" title="More like this">
          <MovieRelated movieId={id} />
        </MovieFeatureSection>
      </div>
    </div>
  )
}
