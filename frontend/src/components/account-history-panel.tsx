import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'
import { Film, History, Trash2 } from 'lucide-react'
import { useAuth } from '../lib/auth'
import { clearHistory, getHistory, type HistoryKind } from '../lib/history-api'
import { Button } from './ui/button'

export function AccountHistoryPanel() {
  const auth = useAuth()
  const owner = auth.user!.id
  const [kind, setKind] = useState<HistoryKind>('movies')
  const [page, setPage] = useState(1)
  const [confirm, setConfirm] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [issue, setIssue] = useState('')
  const [notice, setNotice] = useState('')
  const client = useQueryClient()
  const query = useQuery({
    queryKey: ['account-history', owner, kind, page],
    queryFn: ({ signal }) => getHistory(owner, kind, page, signal),
    enabled: auth.status === 'authenticated',
    retry: false,
    gcTime: 0,
  })
  const data = query.data
  async function clear() {
    setClearing(true)
    setIssue('')
    setNotice('')
    try {
      await client.cancelQueries({ queryKey: ['account-history', owner, kind] })
      await clearHistory(owner, kind, auth.csrf)
      await client.invalidateQueries({
        queryKey: ['account-history', owner, kind],
      })
      setPage(1)
      setConfirm(false)
      setNotice(
        kind === 'movies'
          ? 'Movie-page history cleared'
          : 'Quiz history cleared',
      )
    } catch (problem) {
      setIssue(
        problem instanceof Error
          ? problem.message
          : 'History could not be cleared. Try again.',
      )
    } finally {
      setClearing(false)
    }
  }
  return (
    <section
      className="account-card account-history"
      aria-labelledby="history-title"
    >
      <header className="history-heading">
        <div className="preferences-heading">
          <History size={22} aria-hidden="true" />
          <h2 id="history-title">Your history</h2>
        </div>
        {!!data?.total && (
          <Button
            variant="ghost"
            disabled={clearing || auth.busy || auth.status !== 'authenticated'}
            onClick={() => {
              setConfirm(true)
              setNotice('')
            }}
          >
            <Trash2 size={17} aria-hidden="true" />
            Clear history
          </Button>
        )}
      </header>
      <div className="history-modes" role="group" aria-label="History type">
        {(
          [
            ['movies', 'Recently viewed'],
            ['quizzes', 'Quiz history'],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            aria-pressed={kind === value}
            disabled={clearing}
            onClick={() => {
              setKind(value)
              setPage(1)
              setConfirm(false)
              setIssue('')
              setNotice('')
            }}
          >
            {label}
          </button>
        ))}
      </div>
      {kind === 'movies' && !auth.user!.preferences.track_movie_history && (
        <p className="history-paused">
          Movie-page history is paused. Existing visits remain here.
        </p>
      )}
      {confirm && (
        <div className="history-confirm">
          <p>
            Clear all {kind === 'movies' ? 'movie-page' : 'quiz'} history? This
            cannot be undone.
          </p>
          <div>
            <Button disabled={clearing} onClick={() => void clear()}>
              {clearing ? 'Clearing…' : 'Confirm clear'}
            </Button>
            <Button
              variant="outline"
              disabled={clearing}
              onClick={() => setConfirm(false)}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}
      {issue && (
        <p role="alert" className="collection-form-error">
          {issue}
        </p>
      )}
      {query.isPending ? (
        <p role="status">Loading history…</p>
      ) : query.isError ? (
        <div className="history-empty">
          <p role="alert">Your history could not be loaded.</p>
          <Button variant="outline" onClick={() => void query.refetch()}>
            Retry history
          </Button>
        </div>
      ) : !data?.items.length ? (
        <div className="history-empty">
          <Film size={26} aria-hidden="true" />
          <p>
            {kind === 'movies'
              ? 'Films you visit will appear here.'
              : 'Finish a quiz to save your first round.'}
          </p>
        </div>
      ) : (
        <>
          <ol className="history-list">
            {data.items.map((item) => (
              <li key={item.id}>
                <Link
                  className="history-film"
                  to={`/movies/${item.movie_id}${kind === 'quizzes' ? '#quiz' : ''}`}
                >
                  {item.cover_url ? (
                    <img src={item.cover_url} alt="" loading="lazy" />
                  ) : (
                    <span className="history-poster" aria-hidden="true">
                      <Film size={22} />
                    </span>
                  )}
                  <span>
                    <strong>{item.title}</strong>
                    <time dateTime={item.occurred_at}>
                      {new Intl.DateTimeFormat(undefined, {
                        dateStyle: 'medium',
                        timeStyle: 'short',
                      }).format(new Date(item.occurred_at))}
                    </time>
                  </span>
                </Link>
                {kind === 'quizzes' && (
                  <div className="history-score">
                    <strong>
                      {item.score} / {item.scored_questions}
                    </strong>
                    <span>{item.total_questions} questions</span>
                  </div>
                )}
              </li>
            ))}
          </ol>
          {data.total_pages > 1 && (
            <nav className="history-pagination" aria-label="History pages">
              <Button
                variant="outline"
                disabled={page === 1 || clearing}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </Button>
              <span>
                Page {page} of {data.total_pages}
              </span>
              <Button
                variant="outline"
                disabled={page >= data.total_pages || clearing}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </nav>
          )}
        </>
      )}
      <p className="history-notice" role="status">
        {notice}
      </p>
    </section>
  )
}
