import { ArrowRight, CircleAlert, Film, LoaderCircle } from 'lucide-react'
import { Link } from 'react-router'
import { Button } from './ui/button'

export function LoadingGrid() {
  return (
    <div className="movie-grid" aria-label="Loading movies" aria-busy="true">
      {Array.from({ length: 5 }, (_, index) => (
        <div key={index} className="skeleton-card">
          <div />
          <span />
          <span />
        </div>
      ))}
    </div>
  )
}

export function LoadingPage() {
  return (
    <div className="status-panel" role="status">
      <LoaderCircle className="loading-icon" size={28} aria-hidden="true" />
      <p>Opening this film…</p>
    </div>
  )
}

export function ErrorPanel({ retry }: { retry: () => void }) {
  return (
    <div className="status-panel" role="alert">
      <CircleAlert size={28} aria-hidden="true" />
      <h2>The collection is taking a break.</h2>
      <p>
        We couldn’t reach it. Check that the local app is running, then try
        again.
      </p>
      <Button variant="outline" onClick={retry}>
        Try again
      </Button>
    </div>
  )
}

export function MissingMovie() {
  return (
    <div className="status-panel">
      <Film size={28} aria-hidden="true" />
      <h1>This film isn’t in the collection.</h1>
      <p>Explore one of the available movies instead.</p>
      <Button asChild>
        <Link to="/">
          Back to discovery <ArrowRight size={16} aria-hidden="true" />
        </Link>
      </Button>
    </div>
  )
}
