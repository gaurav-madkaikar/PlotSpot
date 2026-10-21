import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { loadReports, reviewReport } from '../lib/community-api'
import type { CommunityReport } from '../lib/community-contracts'
import { useAuth } from '../lib/auth'
import { Button } from './ui/button'
import { CollectionDialog } from './collection-dialog'
export function CommunityReportPanel({
  owner,
  allowed,
}: {
  owner: string
  allowed: boolean
}) {
  const auth = useAuth()
  const [page, setPage] = useState(1)
  const [state, setState] = useState<'open' | 'resolved'>('open')
  const [target, setTarget] = useState<{
    report: CommunityReport
    action: 'dismiss' | 'hide' | 'restore'
  } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const queue = useQuery({
    queryKey: ['community-reports', owner, allowed, state, page],
    queryFn: ({ signal }) => loadReports(owner, page, allowed, state, signal),
    gcTime: 0,
    retry: false,
  })
  async function review() {
    if (!target || busy) return
    setBusy(true)
    setError('')
    try {
      await reviewReport(
        owner,
        target.report.id,
        target.report.revision,
        target.action,
        auth.csrf,
      )
      setTarget(null)
      await queue.refetch()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Review could not be saved.')
    } finally {
      setBusy(false)
    }
  }
  return (
    <section className="community-moderation" aria-label="Moderator reports">
      <div className="community-heading">
        <h3>Reported posts</h3>
        <div className="community-form-actions">
          <Button
            variant={state === 'open' ? 'outline' : 'ghost'}
            onClick={() => {
              setState('open')
              setPage(1)
            }}
          >
            Pending
          </Button>
          <Button
            variant={state === 'resolved' ? 'outline' : 'ghost'}
            onClick={() => {
              setState('resolved')
              setPage(1)
            }}
          >
            Reviewed
          </Button>
        </div>
      </div>
      {queue.isPending ? (
        <p role="status">Loading reports…</p>
      ) : queue.isError ? (
        <p role="alert">
          Reports could not be loaded.{' '}
          <Button variant="ghost" onClick={() => void queue.refetch()}>
            Retry
          </Button>
        </p>
      ) : (
        <>
          <p className="community-meta">{queue.data.total} reports</p>
          {queue.data.items.map((report) => (
            <article key={report.id} className="community-post">
              <p className="eyebrow">
                {report.reason} · Film {report.movie_id}
              </p>
              {report.title && <h4>{report.title}</h4>}
              <p className="community-body">
                {report.spoiler_locked
                  ? 'Enable spoilers to review this content.'
                  : report.body || 'Post removed.'}
              </p>
              {report.details && (
                <p className="community-body">
                  Report details: {report.details}
                </p>
              )}
              <div className="community-form-actions">
                {report.state === 'open' && (
                  <>
                    <Button
                      variant="outline"
                      onClick={() => {
                        setError('')
                        setTarget({ report, action: 'dismiss' })
                      }}
                    >
                      Dismiss report
                    </Button>
                    {report.content_state === 'visible' && (
                      <Button
                        variant="outline"
                        onClick={() => {
                          setError('')
                          setTarget({ report, action: 'hide' })
                        }}
                      >
                        Hide post
                      </Button>
                    )}
                  </>
                )}
                {report.content_state === 'hidden' && (
                  <Button
                    variant="outline"
                    onClick={() => {
                      setError('')
                      setTarget({ report, action: 'restore' })
                    }}
                  >
                    Restore post
                  </Button>
                )}
              </div>
            </article>
          ))}
          {!queue.data.items.length && <p>No reports to review.</p>}
          <div className="community-form-actions">
            <Button
              variant="ghost"
              disabled={page === 1}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </Button>
            <span>Page {page}</span>
            <Button
              variant="ghost"
              disabled={!queue.data.has_more}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        </>
      )}
      {target && (
        <CollectionDialog
          busy={busy}
          eyebrow="MODERATION"
          title="Confirm review"
          description={`${target.action === 'hide' ? 'Hide this post from the community' : target.action === 'restore' ? 'Restore this post to the community' : 'Dismiss this report'}?`}
          onClose={() => {
            if (!busy) setTarget(null)
          }}
        >
          {error && <p role="alert">{error}</p>}
          <Button disabled={busy} onClick={() => void review()}>
            {busy ? 'Saving…' : 'Confirm'}
          </Button>
        </CollectionDialog>
      )}
    </section>
  )
}
