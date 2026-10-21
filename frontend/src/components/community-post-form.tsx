import { useId, useState } from 'react'
import type { PostDraft } from '../lib/community-contracts'
import { Button } from './ui/button'
export function CommunityPostForm({
  thread = false,
  initial,
  label,
  busy,
  onSubmit,
  onCancel,
}: {
  thread?: boolean
  initial?: PostDraft
  label: string
  busy: boolean
  onSubmit: (draft: PostDraft) => Promise<boolean>
  onCancel: () => void
}) {
  const id = useId()
  const [title, setTitle] = useState(initial?.title ?? '')
  const [body, setBody] = useState(initial?.body ?? '')
  const [spoilers, setSpoilers] = useState(initial?.spoilers ?? false)
  const [error, setError] = useState('')
  return (
    <form
      className="community-form"
      aria-label={label}
      onSubmit={async (e) => {
        e.preventDefault()
        if (!body.trim() || (thread && !title.trim())) {
          setError('Add your ' + (thread ? 'title and message.' : 'reply.'))
          return
        }
        setError('')
        await onSubmit({
          ...(thread ? { title: title.trim() } : {}),
          body: body.trim(),
          spoilers,
        })
      }}
    >
      {thread && (
        <div>
          <label htmlFor={`${id}-title`}>Discussion title</label>
          <input
            id={`${id}-title`}
            maxLength={140}
            value={title}
            disabled={busy}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>
      )}
      <div>
        <label htmlFor={`${id}-body`}>
          {thread ? 'Your post' : 'Your reply'}
        </label>
        <textarea
          id={`${id}-body`}
          rows={4}
          maxLength={thread ? 5000 : 2000}
          value={body}
          disabled={busy}
          onChange={(e) => setBody(e.target.value)}
        />
      </div>
      <label className="community-spoiler-label">
        <input
          type="checkbox"
          checked={spoilers}
          disabled={busy}
          onChange={(e) => setSpoilers(e.target.checked)}
        />
        Contains spoilers
      </label>
      {error && (
        <p role="alert" className="collection-form-error">
          {error}
        </p>
      )}
      <div className="community-form-actions">
        <Button type="submit" disabled={busy}>
          {busy ? 'Saving…' : label}
        </Button>
        <Button
          type="button"
          variant="ghost"
          disabled={busy}
          onClick={onCancel}
        >
          Cancel
        </Button>
      </div>
    </form>
  )
}
