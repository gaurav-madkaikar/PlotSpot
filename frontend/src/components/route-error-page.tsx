import { Button } from './ui/button'

export function RouteErrorPage() {
  return (
    <main className="route-error-page">
      <a href="/" className="route-error-brand">
        PlotSpot
      </a>
      <section role="alert" className="status-panel">
        <h1>Something interrupted this page.</h1>
        <p>Try reloading, or return to discovery to find your next film.</p>
        <div className="route-error-actions">
          <Button onClick={() => window.location.reload()}>Reload page</Button>
          <a href="/" className="text-button">
            Back to discovery
          </a>
        </div>
      </section>
    </main>
  )
}
