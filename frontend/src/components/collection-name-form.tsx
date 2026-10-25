import { useId, useState } from 'react'
import { Plus } from 'lucide-react'
import { useCollection, type NamedCollection } from '../lib/collection'
import { Button } from './ui/button'

export function CollectionNameForm({
  collection,
  onComplete,
}: {
  collection?: NamedCollection
  onComplete: (id: string) => void
}) {
  const { createCollection, renameCollection, loading, saving } =
    useCollection()
  const [name, setName] = useState(collection?.name ?? '')
  const [error, setError] = useState('')
  const inputId = useId()
  return (
    <form
      className="collection-name-form"
      noValidate
      onSubmit={async (event) => {
        event.preventDefault()
        if (collection) {
          const issue = await renameCollection(collection.id, name)
          if (issue) {
            setError(issue)
            return
          }
          onComplete(collection.id)
        } else {
          const result = await createCollection(name)
          if (result.error) {
            setError(result.error)
            return
          }
          setName('')
          setError('')
          onComplete(result.id!)
        }
      }}
    >
      <label htmlFor={inputId}>
        {collection ? 'Collection name' : 'New collection name'}
      </label>
      <div className="collection-name-row">
        <input
          id={inputId}
          disabled={loading || saving}
          value={name}
          maxLength={60}
          placeholder="Weekend favourites"
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${inputId}-error` : undefined}
          onChange={(event) => {
            setName(event.target.value)
            setError('')
          }}
        />
        <Button type="submit" variant="outline" disabled={loading || saving}>
          {!collection && <Plus size={16} aria-hidden="true" />}
          {saving ? 'Saving…' : collection ? 'Save name' : 'Create'}
        </Button>
      </div>
      {error && (
        <p
          className="collection-form-error"
          id={`${inputId}-error`}
          role="alert"
        >
          {error}
        </p>
      )}
    </form>
  )
}
