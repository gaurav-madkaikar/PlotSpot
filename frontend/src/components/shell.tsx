import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getHealth } from '../lib/api'
import {
  Link,
  NavLink,
  Outlet,
  ScrollRestoration,
  useLocation,
} from 'react-router'
import { useCollection } from '../lib/collection'
import { useAuth } from '../lib/auth'

export function Shell() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: ({ signal }) => getHealth(signal),
  })
  const auth = useAuth()
  const { saved, message, storageWarning } = useCollection()
  const { pathname, state } = useLocation()
  const discoverTo =
    pathname.startsWith('/movies/') &&
    typeof state?.returnTo === 'string' &&
    /^\/(?:\?|#|$)/.test(state.returnTo)
      ? state.returnTo
      : '/'
  useEffect(() => {
    document.getElementById('main-content')?.focus({ preventScroll: true })
  }, [pathname])
  return (
    <>
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>
      <header className="site-header">
        <div className="header-inner">
          <Link to="/" className="brand" aria-label="PlotSpot home">
            <span className="brand-mark" aria-hidden="true">
              <img src="/plotspot-reel.svg" width="40" height="40" alt="" />
            </span>
            <span>
              PlotSpot<span className="brand-dot">.</span>
            </span>
          </Link>
          <span className="brand-caption">
            Experience content like never before
          </span>
          <nav aria-label="Main navigation">
            <NavLink to={discoverTo} end>
              Discover
            </NavLink>
            <NavLink to="/collections">
              <span>Collections</span>
            </NavLink>
            <NavLink
              to="/account"
              aria-label={auth.user ? 'Account' : 'Sign in'}
            >
              <span>{auth.user ? 'Account' : 'Sign in'}</span>
            </NavLink>
          </nav>
        </div>
      </header>
      <main id="main-content" tabIndex={-1}>
        <Outlet />
      </main>
      <footer className="site-footer site-footer--dark">
        <div className="footer-inner">
          <div className="footer-brand">
            <Link to="/" aria-label="PlotSpot home in footer">
              <img src="/plotspot-reel.svg" width="28" height="28" alt="" />
              <span>PlotSpot</span>
            </Link>
            <p>Experience content like never before</p>
          </div>
          <nav aria-label="Footer navigation">
            <Link to="/">Explore films</Link>
            <Link to="/collections">Your collections</Link>
            <Link to="/about">About PlotSpot</Link>
          </nav>
        </div>
        <div className="footer-meta">
          <span>© {new Date().getFullYear()} PlotSpot</span>
          <Link to="/about">
            {health.data?.data_source === 'tmdb'
              ? 'Movie data · TMDB'
              : health.data?.data_source === 'demo'
                ? 'Demo data · Original illustrations'
                : 'Data sources and credits'}
          </Link>
        </div>
      </footer>
      <div className="sr-only" role="status" aria-live="polite">
        {message}
      </div>
      {auth.status === 'error' && (
        <div className="storage-warning" role="alert">
          <span>{auth.error}</span>
          <button onClick={() => void auth.refresh()}>Retry account</button>
        </div>
      )}
      {storageWarning && (
        <div className="storage-warning" role="status">
          {storageWarning}
        </div>
      )}
      {auth.status === 'guest' &&
        saved.length > 0 &&
        !['/account', '/collections', '/collection'].includes(pathname) && (
          <div className="guest-save-prompt" role="status">
            <Link to="/account?returnTo=/collections">
              Sign in to keep your saves
            </Link>
          </div>
        )}
      <ScrollRestoration
        getKey={(location) => location.pathname + location.search}
      />
    </>
  )
}
