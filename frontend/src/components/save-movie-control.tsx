import { useState } from 'react'
import { Bookmark, Check, FolderHeart } from 'lucide-react'
import { useCollection } from '../lib/collection'
import { Button } from './ui/button'
import { CollectionDialog } from './collection-dialog'
import { CollectionNameForm } from './collection-name-form'

function MovieCollectionPicker({
  movieId,
  title,
  onClose,
}: {
  movieId: number
  title: string
  onClose: () => void
}) {
  const { collections, setMovieCollections, removeSaved, loading, saving } =
    useCollection()
  const [selected, setSelected] = useState(() =>
    collections
      .filter((collection) => collection.movieIds.includes(movieId))
      .map((collection) => collection.id),
  )
  return (
    <CollectionDialog
      title={title}
      description="Choose any other collections for this film."
      onClose={onClose}
    >
      <fieldset className="collection-picker-list" disabled={loading || saving}>
        <legend className="sr-only">Collections for {title}</legend>
        <label className="collection-picker-row collection-picker-default">
          <input type="checkbox" checked disabled />
          <span>
            <strong>All saved</strong>
            <small>Every film you save</small>
          </span>
          <Bookmark size={18} aria-hidden="true" />
        </label>
        {collections.map((collection) => (
          <label key={collection.id} className="collection-picker-row">
            <input
              type="checkbox"
              checked={selected.includes(collection.id)}
              onChange={(event) =>
                setSelected((current) =>
                  event.target.checked
                    ? [...current, collection.id]
                    : current.filter((id) => id !== collection.id),
                )
              }
            />
            <span>
              <strong>{collection.name}</strong>
              <small>
                {collection.movieIds.length}{' '}
                {collection.movieIds.length === 1 ? 'film' : 'films'}
              </small>
            </span>
            <FolderHeart size={18} aria-hidden="true" />
          </label>
        ))}
      </fieldset>
      <CollectionNameForm
        onComplete={(id) => setSelected((current) => [...current, id])}
      />
      <footer className="collection-dialog-actions">
        <button
          type="button"
          className="collection-remove"
          disabled={loading || saving}
          onClick={async () => {
            if (await removeSaved(movieId)) onClose()
          }}
        >
          Remove from saved
        </button>
        <Button
          type="button"
          disabled={loading || saving}
          onClick={async () => {
            if (await setMovieCollections(movieId, selected)) onClose()
          }}
        >
          Done
        </Button>
      </footer>
    </CollectionDialog>
  )
}

export function SaveMovieControl({
  movieId,
  title,
  compact = false,
}: {
  movieId: number
  title: string
  compact?: boolean
}) {
  const { saved, saveMovie, loading, saving, loadError } = useCollection()
  const [open, setOpen] = useState(false)
  const isSaved = saved.includes(movieId)
  const label = isSaved
    ? `Manage collections for ${title}`
    : `Save ${title} to collection`
  async function openPicker() {
    if (!isSaved && !(await saveMovie(movieId))) return
    setOpen(true)
  }
  const icon = isSaved ? (
    <Check size={compact ? 18 : 17} aria-hidden="true" />
  ) : (
    <Bookmark size={compact ? 18 : 17} aria-hidden="true" />
  )
  return (
    <>
      {compact ? (
        <button
          type="button"
          className="save-button"
          aria-label={label}
          aria-pressed={isSaved}
          aria-haspopup="dialog"
          disabled={loading || saving || loadError}
          onClick={() => void openPicker()}
        >
          {icon}
        </button>
      ) : (
        <Button
          type="button"
          variant={isSaved ? 'outline' : 'default'}
          aria-label={label}
          aria-haspopup="dialog"
          disabled={loading || saving || loadError}
          onClick={() => void openPicker()}
        >
          {icon}
          {isSaved ? 'Manage collections' : 'Save to collection'}
        </Button>
      )}
      {open && (
        <MovieCollectionPicker
          movieId={movieId}
          title={title}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  )
}
