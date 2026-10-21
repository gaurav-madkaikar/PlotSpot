import { useState } from 'react'
import type {
  CommunityPost,
  PostKind,
  PostDraft,
} from '../lib/community-contracts'
import { CollectionDialog } from './collection-dialog'
import { CommunityPostForm } from './community-post-form'
import { Button } from './ui/button'
export type PostAction = {
  post: CommunityPost
  kind: PostKind
  action: 'edit' | 'delete' | 'report'
}
export function CommunityPostDialog({
  target,
  busy,
  error,
  onClose,
  onEdit,
  onDelete,
  onReport,
}: {
  target: PostAction
  busy: boolean
  error: string
  onClose: () => void
  onEdit: (draft: PostDraft) => Promise<boolean>
  onDelete: () => void
  onReport: (reason: string, details: string) => void
}) {
  const [reason, setReason] = useState('spam')
  const [details, setDetails] = useState('')
  const title = {
    edit: 'Edit your post',
    delete: 'Remove your post?',
    report: 'Report this post',
  }[target.action]
  return (
    <CollectionDialog
      busy={busy}
      title={title}
      eyebrow="DISCUSSION"
      description={
        target.action === 'delete'
          ? 'Your post will be removed. Replies remain in the conversation.'
          : target.action === 'report'
            ? 'Reports are reviewed by a moderator.'
            : 'Keep story details labelled as spoilers.'
      }
      onClose={() => {
        if (!busy) onClose()
      }}
    >
      {error && (
        <p role="alert" className="collection-form-error">
          {error}
        </p>
      )}
      {target.action === 'edit' ? (
        <CommunityPostForm
          thread={target.kind === 'thread'}
          initial={{
            ...(target.kind === 'thread'
              ? { title: target.post.title ?? '' }
              : {}),
            body: target.post.body ?? '',
            spoilers: target.post.spoilers,
          }}
          label="Save changes"
          busy={busy}
          onSubmit={onEdit}
          onCancel={onClose}
        />
      ) : target.action === 'delete' ? (
        <div className="community-form-actions">
          <Button disabled={busy} onClick={onDelete}>
            {busy ? 'Removing…' : 'Remove post'}
          </Button>
          <Button disabled={busy} variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </div>
      ) : (
        <form
          className="community-form"
          onSubmit={(e) => {
            e.preventDefault()
            onReport(reason, details)
          }}
        >
          <div>
            <label htmlFor="report-reason">Reason</label>
            <select
              id="report-reason"
              value={reason}
              disabled={busy}
              onChange={(e) => setReason(e.target.value)}
            >
              <option value="spam">Spam</option>
              <option value="harassment">Harassment</option>
              <option value="spoiler">Unlabelled spoilers</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div>
            <label htmlFor="report-details">Details (optional)</label>
            <textarea
              id="report-details"
              maxLength={500}
              value={details}
              disabled={busy}
              onChange={(e) => setDetails(e.target.value)}
            />
          </div>
          <Button disabled={busy} type="submit">
            {busy ? 'Sending…' : 'Send report'}
          </Button>
        </form>
      )}
    </CollectionDialog>
  )
}
