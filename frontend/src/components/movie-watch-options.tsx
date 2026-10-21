import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getWatchOptions, getWatchRegions } from '../lib/api'
import { Button } from './ui/button'

const kinds = {
  subscription: 'Subscription',
  free: 'Free',
  ads: 'Free with ads',
  rent: 'Rent',
  buy: 'Buy',
}
const countryKey = 'frame.watch.country.v1'
function initialCountry() {
  try {
    const saved = localStorage.getItem(countryKey)
    return saved && /^[A-Z]{2}$/.test(saved) ? saved : 'IN'
  } catch {
    return 'IN'
  }
}
function ProviderLogo({ url, name }: { url: string | null; name: string }) {
  const [failed, setFailed] = useState(false)
  return url && !failed ? (
    <img src={url} alt="" loading="lazy" onError={() => setFailed(true)} />
  ) : (
    <span className="watch-logo-placeholder" aria-hidden="true">
      {name[0]}
    </span>
  )
}
export function MovieWatchOptions({ movieId }: { movieId: number }) {
  const [country, setCountry] = useState(initialCountry)
  const regions = useQuery({
    queryKey: ['watch-regions'],
    queryFn: ({ signal }) => getWatchRegions(signal),
    staleTime: 86400000,
    retry: 1,
  })
  const options = useQuery({
    queryKey: ['watch-options', movieId, country],
    queryFn: async ({ signal }) => {
      const result = await getWatchOptions(movieId, country, signal)
      if (result.movie_id !== movieId || result.country !== country)
        throw new Error('Mismatched availability')
      return result
    },
    staleTime: 600000,
    retry: 1,
  })
  const names = new Intl.DisplayNames(['en'], { type: 'region' })
  const countries = regions.data?.items ?? []
  return (
    <section
      className="watch-options question-panel"
      aria-labelledby="watch-title"
    >
      <header className="feature-heading">
        <div>
          <p className="eyebrow">YOUR NEXT MOVIE NIGHT</p>
          <h2 id="watch-title">Where to watch</h2>
        </div>
        <div className="watch-country">
          <label htmlFor="watch-country">Country</label>
          <select
            id="watch-country"
            value={country}
            onChange={(event) => {
              setCountry(event.target.value)
              try {
                localStorage.setItem(countryKey, event.target.value)
              } catch {
                /* Selection still works without browser storage. */
              }
            }}
          >
            {!countries.some((item) => item.code === country) && (
              <option value={country}>{names.of(country) ?? country}</option>
            )}
            {countries.map((item) => (
              <option key={item.code} value={item.code}>
                {item.name}
              </option>
            ))}
          </select>
        </div>
      </header>
      {regions.isError && (
        <p className="watch-note">
          Country choices could not be loaded.{' '}
          <button
            type="button"
            className="text-link"
            onClick={() => void regions.refetch()}
          >
            Retry countries
          </button>
        </p>
      )}
      {options.isPending && <p role="status">Checking watch options…</p>}
      {options.isError && (
        <div>
          <p role="status">Watch options are unavailable right now.</p>
          <Button variant="outline" onClick={() => void options.refetch()}>
            Retry watch options
          </Button>
        </div>
      )}
      {options.data && (
        <>
          {options.data.stale && (
            <p className="watch-note" role="status">
              Showing previously checked options. Availability could not be
              refreshed.
            </p>
          )}
          {options.data.groups.length === 0 ? (
            <p>
              No watch options are listed for {names.of(country) ?? country}.
            </p>
          ) : (
            <div className="watch-groups">
              {options.data.groups.map((group) => (
                <div key={group.kind}>
                  <h3>{kinds[group.kind]}</h3>
                  <ul>
                    {group.providers.map((provider) => (
                      <li key={provider.id}>
                        <ProviderLogo
                          url={provider.logo_url}
                          name={provider.name}
                        />
                        <span>{provider.name}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
          {options.data.watch_url && (
            <a
              className="button button-outline watch-link"
              href={options.data.watch_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              View watch options
            </a>
          )}
          {options.data.checked_at && (
            <p className="watch-note">
              Checked{' '}
              {new Intl.DateTimeFormat('en', { dateStyle: 'medium' }).format(
                new Date(options.data.checked_at),
              )}
              . Availability may change.
            </p>
          )}
        </>
      )}
      <p className="watch-attribution">
        Watch availability by{' '}
        <a
          href="https://www.justwatch.com/"
          target="_blank"
          rel="noopener noreferrer"
        >
          JustWatch
        </a>
      </p>
    </section>
  )
}
