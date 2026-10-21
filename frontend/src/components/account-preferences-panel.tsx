import { useState } from 'react'
import { Settings2 } from 'lucide-react'
import { useAuth } from '../lib/auth'
import type { AccountPreferences } from '../lib/account-contracts'
import { Button } from './ui/button'

export function AccountPreferencesPanel() {
  const auth = useAuth()
  const saved = auth.user!.preferences
  const [draft, setDraft] = useState<AccountPreferences>(saved)
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState('')
  const changed =
    draft.allow_spoilers !== saved.allow_spoilers ||
    draft.include_adult !== saved.include_adult ||
    draft.track_movie_history !== saved.track_movie_history
  const stale = draft.revision !== saved.revision
  async function save(event: React.FormEvent) {
    event.preventDefault()
    setSaving(true)
    setNotice('')
    if (await auth.updatePreferences(draft)) {
      setDraft({ ...draft, revision: draft.revision + 1 })
      setNotice('Preferences saved')
    }
    setSaving(false)
  }
  return (
    <section
      className="account-card account-preferences"
      aria-labelledby="preferences-title"
    >
      <div className="preferences-heading">
        <Settings2 size={22} aria-hidden="true" />
        <h2 id="preferences-title">Viewing preferences</h2>
      </div>
      <p>Set how you discover and explore films.</p>
      <form onSubmit={(event) => void save(event)} aria-busy={saving}>
        {(
          [
            [
              'allow_spoilers',
              'Allow spoilers by default',
              'Show story and ending details. Movie controls can override this for your current visit.',
            ],
            [
              'track_movie_history',
              'Save movie-page history',
              'Keep a history of films you visit. Turn off to stop recording new visits.',
            ],
            [
              'include_adult',
              'Include adult films in discovery',
              'Include films marked adult by TMDB. Other films may still contain mature themes.',
            ],
          ] as const
        ).map(([field, label, help]) => (
          <div className="preference-row" key={field}>
            <div>
              <label htmlFor={`preference-${field}`}>{label}</label>
              <p id={`help-${field}`}>{help}</p>
            </div>
            <label className="preference-switch">
              <input
                id={`preference-${field}`}
                type="checkbox"
                role="switch"
                aria-describedby={`help-${field}`}
                checked={draft[field]}
                disabled={auth.busy || auth.status !== 'authenticated'}
                onChange={(event) => {
                  setDraft({ ...draft, [field]: event.target.checked })
                  setNotice('')
                }}
              />
              <span className="spoiler-track" aria-hidden="true">
                <span />
              </span>
            </label>
          </div>
        ))}
        {stale && (
          <div className="preferences-conflict" role="alert">
            <p>
              Settings changed in another tab. Load the latest preferences
              before editing again.
            </p>
            <Button
              type="button"
              variant="outline"
              disabled={auth.busy}
              onClick={() => {
                setDraft(saved)
                setNotice('Latest preferences loaded')
              }}
            >
              Load latest preferences
            </Button>
          </div>
        )}
        {auth.error && (
          <p role="alert" className="collection-form-error">
            {auth.error}
          </p>
        )}
        <div className="preferences-actions">
          <Button
            type="submit"
            disabled={
              !changed || stale || auth.busy || auth.status !== 'authenticated'
            }
          >
            {saving ? 'Saving…' : 'Save preferences'}
          </Button>
          <Button
            type="button"
            variant="ghost"
            disabled={
              auth.busy ||
              stale ||
              (!draft.allow_spoilers &&
                draft.include_adult &&
                draft.track_movie_history)
            }
            onClick={() => {
              setDraft({
                ...draft,
                allow_spoilers: false,
                include_adult: true,
                track_movie_history: true,
              })
              setNotice('Defaults restored. Save to apply.')
            }}
          >
            Reset to defaults
          </Button>
        </div>
        <p className="preferences-notice" role="status" aria-live="polite">
          {notice || (changed ? 'Unsaved changes' : '')}
        </p>
      </form>
    </section>
  )
}
