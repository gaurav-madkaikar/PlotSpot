import { useState } from 'react'
import {
  Users,
  CalendarDays,
  Globe2,
  Clapperboard,
  Wallet,
  TrendingUp,
} from 'lucide-react'
import type { Movie } from '../lib/contracts'

const dollars = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
})

function CastPortrait({ name, url }: { name: string; url: string | null }) {
  const [failed, setFailed] = useState(false)
  return url && !failed ? (
    <img src={url} alt={name} loading="lazy" onError={() => setFailed(true)} />
  ) : (
    <div className="cast-portrait-placeholder" aria-hidden="true">
      {name
        .split(' ')
        .map((n) => n[0])
        .slice(0, 2)
        .join('')}
    </div>
  )
}

export function MovieDetails({ movie }: { movie: Movie }) {
  const meta = movie.detail_metadata
  const release = meta?.release_date
    ? new Intl.DateTimeFormat('en-US', {
        day: 'numeric',
        month: 'long',
        year: 'numeric',
        timeZone: 'UTC',
      }).format(new Date(`${meta.release_date}T00:00:00Z`))
    : 'Not available'
  const details = [
    { label: 'Release date', value: release, icon: CalendarDays },
    {
      label: 'Spoken languages',
      value: meta?.spoken_languages.join(', ') || 'Not available',
      icon: Globe2,
    },
    {
      label: 'Budget',
      value: meta?.budget ? dollars.format(meta.budget) : 'Not reported',
      icon: Wallet,
    },
    {
      label: 'Worldwide revenue',
      value: meta?.revenue ? dollars.format(meta.revenue) : 'Not reported',
      icon: TrendingUp,
    },
  ]
  return (
    <section className="film-at-a-glance" aria-labelledby="film-details-title">
      <div className="overview-section-heading">
        <div>
          <p className="eyebrow">BEHIND THE FILM</p>
          <h2 id="film-details-title">Film details</h2>
        </div>
        {meta?.status && <span className="film-status">{meta.status}</span>}
      </div>
      <div className="film-stat-grid">
        <dl className="film-detail-grid">
          {details.map(({ label, value, icon: Icon }) => (
            <div key={label}>
              <dt>
                <Icon size={17} aria-hidden="true" />
                {label}
              </dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      </div>
      {meta?.production_companies.length ||
      meta?.production_countries.length ? (
        <div className="film-production">
          {!!meta?.production_companies.length && (
            <div>
              <h3>
                <Clapperboard size={18} aria-hidden="true" />
                Production companies
              </h3>
              <div className="production-tags">
                {meta.production_companies.map((name) => (
                  <span key={name}>{name}</span>
                ))}
              </div>
            </div>
          )}
          {!!meta?.production_countries.length && (
            <div>
              <h3>Production countries</h3>
              <p>{meta.production_countries.join(', ')}</p>
            </div>
          )}
        </div>
      ) : (
        <p className="film-metadata-note">
          Production details are not available yet.
        </p>
      )}
      {meta?.original_title && meta.original_title !== movie.title && (
        <p className="film-metadata-note">
          Original title: {meta.original_title}
        </p>
      )}
      <p className="film-metadata-note">
        {movie.source === 'tmdb'
          ? 'Ratings and production data from TMDB. Financial figures in USD.'
          : 'Sample movie details.'}
      </p>
    </section>
  )
}

export function MovieCast({ movie }: { movie: Movie }) {
  const [expanded, setExpanded] = useState(false)
  const meta = movie.detail_metadata
  const credits = meta?.cast_credits.length
    ? meta.cast_credits
    : movie.cast.map((name) => ({ name, character: null, profile_url: null }))
  const visible = expanded ? credits : credits.slice(0, 6)
  const creativeCredits = meta?.creative_credits ?? []
  const creativeRoles = [...new Set(creativeCredits.map((credit) => credit.role))]
  return (
    <section id="cast" className="film-cast" aria-labelledby="film-cast-title">
      <div className="overview-section-heading">
        <div>
          <p className="eyebrow">THE PEOPLE ON SCREEN</p>
          <h2 id="film-cast-title">Cast & characters</h2>
        </div>
        <Users size={22} aria-hidden="true" />
      </div>
      {credits.length === 0 ? (
        <p>Cast details unavailable.</p>
      ) : (
        <div className="cast-credit-grid" id="cast-credits">
          {visible.map((credit, i) => (
            <article className="cast-credit-card" key={`${credit.name}-${i}`}>
              <CastPortrait name={credit.name} url={credit.profile_url} />
              <div>
                <h3>{credit.name}</h3>
                <p>{credit.character || 'Role not listed'}</p>
              </div>
            </article>
          ))}
        </div>
      )}
      {credits.length > 6 && (
        <button
          type="button"
          className="cast-expand"
          aria-expanded={expanded}
          aria-controls="cast-credits"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? 'Show less' : `View all ${credits.length} cast members`}
        </button>
      )}
      {creativeRoles.length > 0 && (
        <div className="creative-team">
          <h3>Creative team</h3>
          <dl>
            {creativeRoles.map((role) => (
              <div key={role}>
                <dt>{role}</dt>
                <dd>
                  {creativeCredits
                    .filter((credit) => credit.role === role)
                    .map((credit) => credit.name)
                    .join(', ')}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </section>
  )
}
