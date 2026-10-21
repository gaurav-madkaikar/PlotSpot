import { useState } from 'react'
import { BookmarkPlus, Check } from 'lucide-react'
import { useAuth } from '../lib/auth'
import { useCollection } from '../lib/collection'
import { readCollection } from '../lib/collection-storage'
import { Button } from './ui/button'

// Keep guest preservation explicit, close to the collection being changed.
export function CollectionVisitImport() {
  const auth = useAuth()
  const personal = useCollection()
  const [visit] = useState(readCollection)
  const [imported, setImported] = useState(false)
  const hasSaves =
    visit.state.saved.length ||
    visit.state.collections.length ||
    visit.state.watched.length
  if (!auth.user || !hasSaves || visit.warning) return null
  return (
    <section
      className="collection-visit-import"
      aria-label="Saves from this visit"
    >
      {imported ? (
        <>
          <Check size={20} aria-hidden="true" />
          <p role="status">Saves added to your account</p>
        </>
      ) : (
        <>
          <BookmarkPlus size={22} aria-hidden="true" />
          <div>
            <strong>Keep your saves from this visit</strong>
            <p>Add these films, collections and preferences to your account</p>
          </div>
          <Button
            variant="outline"
            disabled={
              personal.loading ||
              personal.saving ||
              personal.loadError ||
              auth.busy
            }
            onClick={async () => {
              if (await personal.importBrowser()) setImported(true)
            }}
          >
            {personal.saving ? 'Saving…' : 'Keep these saves'}
          </Button>
        </>
      )}
    </section>
  )
}
