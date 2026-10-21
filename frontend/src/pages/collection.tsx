import { useState } from 'react'
import { useQueries } from '@tanstack/react-query'
import { Bookmark, FolderHeart, Plus, Pencil, Trash2 } from 'lucide-react'
import { Link, useSearchParams } from 'react-router'
import { ApiError, getMovie } from '../lib/api'
import { useCollection } from '../lib/collection'
import { useAuth } from '../lib/auth'
import { MovieCard } from '../components/movie-card'
import { ErrorPanel, LoadingGrid } from '../components/status-panel'
import { Button } from '../components/ui/button'
import { CollectionDialog } from '../components/collection-dialog'
import { CollectionVisitImport } from '../components/collection-visit-import'
import { CollectionNameForm } from '../components/collection-name-form'

export function CollectionPage() {
  const {
    saved,
    collections,
    removeSaved,
    deleteCollection,
    loading,
    saving,
    loadError,
    retry,
  } = useCollection()
  const auth = useAuth()
  const [params, setParams] = useSearchParams()
  const [action, setAction] = useState<'create' | 'rename' | 'delete' | null>(
    null,
  )
  const selected = collections.find(
    (collection) => collection.id === params.get('collection'),
  )
  const ids = selected?.movieIds ?? saved
  const movies = useQueries({
    queries: ids.map((id) => ({
      queryKey: ['movie', id],
      queryFn: ({ signal }: { signal: AbortSignal }) => getMovie(id, signal),
      retry: (count: number, error: Error) =>
        !(error instanceof ApiError && error.status === 404) && count < 1,
    })),
  })
  const films = movies.flatMap((movie) => (movie.data ? [movie.data] : []))
  const pending = movies.some((movie) => movie.isPending)
  const failed = movies.some((movie) => movie.isError)
  const countLabel = (count: number) =>
    `${count} ${count === 1 ? 'film' : 'films'}`
  return (
    <div className="page-width collection-page">
      <div className="collection-page-heading">
        <div>
          <p className="eyebrow">YOUR LIBRARY</p>
          <h1>Your collections</h1>
          <p className="page-intro">
            {auth.user ? (
              'Organise your saved films for every occasion'
            ) : (
              <>
                <Link to="/account?returnTo=/collections">Sign in</Link> to keep
                your films and collections
              </>
            )}
          </p>
        </div>
        <Button
          type="button"
          disabled={loading || saving || loadError}
          onClick={() => setAction('create')}
        >
          <Plus size={17} aria-hidden="true" />
          New collection
        </Button>
      </div>
      <CollectionVisitImport />
      <nav className="collection-views" aria-label="Your collections">
        <Link to="/collections" aria-current={!selected ? 'page' : undefined}>
          <Bookmark size={17} aria-hidden="true" />
          <span>All saved</span>
          {saved.length > 0 && <small>{saved.length}</small>}
        </Link>
        {collections.map((collection) => (
          <Link
            key={collection.id}
            to={`/collections?collection=${encodeURIComponent(collection.id)}`}
            aria-current={selected?.id === collection.id ? 'page' : undefined}
          >
            <FolderHeart size={17} aria-hidden="true" />
            <span>{collection.name}</span>
            {collection.movieIds.length > 0 && (
              <small>{collection.movieIds.length}</small>
            )}
          </Link>
        ))}
      </nav>
      {(selected || ids.length > 0) && (
        <div className="collection-view-heading">
          <div>
            {selected && (
              <div className="collection-title-row">
                <h2>{selected.name}</h2>
                <div className="collection-view-actions">
                  <Button
                    type="button"
                    variant="ghost"
                    aria-label="Rename"
                    title="Rename collection"
                    disabled={loading || saving || loadError}
                    onClick={() => setAction('rename')}
                  >
                    <Pencil size={21} aria-hidden="true" />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    aria-label="Delete collection"
                    title="Delete collection"
                    disabled={loading || saving || loadError}
                    onClick={() => setAction('delete')}
                  >
                    <Trash2 size={21} aria-hidden="true" />
                  </Button>
                </div>
              </div>
            )}
            {!loading && !loadError && ids.length > 0 && (
              <p className="collection-result-count">
                {countLabel(ids.length)}
              </p>
            )}
          </div>
        </div>
      )}
      {loadError ? (
        <div role="alert" className="status-panel">
          <p>Your account collection could not be loaded.</p>
          <Button onClick={retry}>Retry collection</Button>
        </div>
      ) : loading || pending ? (
        <LoadingGrid />
      ) : (
        <>
          {failed && (
            <>
              <ErrorPanel
                retry={() => movies.forEach((movie) => void movie.refetch())}
              />
              <p>Some saved films are unavailable right now.</p>
              {movies.map((movie, index) =>
                movie.isError ? (
                  <div className="results-line" key={ids[index]}>
                    <span>Saved movie #{ids[index]} is unavailable.</span>
                    <Button
                      variant="outline"
                      disabled={saving}
                      onClick={() => void removeSaved(ids[index])}
                    >
                      Remove unavailable movie #{ids[index]}
                    </Button>
                  </div>
                ) : null,
              )}
            </>
          )}
          {films.length > 0 ? (
            <div className="movie-grid">
              {films.map((movie) => (
                <MovieCard key={movie.id} movie={movie} />
              ))}
            </div>
          ) : (
            !failed && (
              <div className="status-panel collection-empty">
                {selected ? (
                  <FolderHeart size={30} aria-hidden="true" />
                ) : (
                  <Bookmark size={30} aria-hidden="true" />
                )}
                <h2>
                  {selected
                    ? 'No films in this collection'
                    : 'Start your film collection'}
                </h2>
                <p>
                  {selected
                    ? 'Choose this collection when saving a film'
                    : 'Save films from Discover to find them here'}
                </p>
                <Button asChild>
                  <Link to="/">Find a film</Link>
                </Button>
              </div>
            )
          )}
        </>
      )}
      {action === 'create' && (
        <CollectionDialog
          title="New collection"
          description="Name your collection to organise saved films"
          onClose={() => setAction(null)}
        >
          <CollectionNameForm
            onComplete={(id) => {
              setAction(null)
              setParams({ collection: id })
            }}
          />
        </CollectionDialog>
      )}
      {action === 'rename' && selected && (
        <CollectionDialog
          title="Rename collection"
          description="Update the name without changing your saved films"
          onClose={() => setAction(null)}
        >
          <CollectionNameForm
            collection={selected}
            onComplete={() => setAction(null)}
          />
        </CollectionDialog>
      )}
      {action === 'delete' && selected && (
        <CollectionDialog
          title={`Delete ${selected.name}?`}
          description="Only this collection will be deleted. Its films will stay in All saved."
          onClose={() => setAction(null)}
        >
          <div className="collection-dialog-actions">
            <Button
              type="button"
              variant="outline"
              onClick={() => setAction(null)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              disabled={saving}
              onClick={async () => {
                if (await deleteCollection(selected.id)) {
                  setAction(null)
                  setParams({})
                }
              }}
            >
              Delete collection
            </Button>
          </div>
        </CollectionDialog>
      )}
    </div>
  )
}
