import { useEffect, useRef, useState } from 'react'
import { useAuth } from './auth'
import { recordVisit } from './history-api'
import type { Movie } from './contracts'

export function useMovieVisit(movie: Movie | undefined) {
  const auth = useAuth()
  const owner = auth.user?.id
  const enabled =
    auth.status === 'authenticated' &&
    auth.user?.preferences.track_movie_history === true
  const visit = useRef<{ key: string; id: string; recorded: boolean } | null>(
    null,
  )
  const [issue, setIssue] = useState('')
  const [retries, setRetries] = useState(0)
  useEffect(() => {
    if (!owner || !enabled || !movie) return
    const key = `${owner}:${movie.id}`
    if (visit.current?.key !== key) {
      visit.current = { key, id: crypto.randomUUID(), recorded: false }
      setIssue('')
    }
    if (visit.current.recorded) return
    const event = visit.current
    const controller = new AbortController()
    void recordVisit(owner, movie.id, event.id, auth.csrf, controller.signal)
      .then(() => {
        if (!controller.signal.aborted && visit.current === event) {
          event.recorded = true
          setIssue('')
        }
      })
      .catch(() => {
        if (!controller.signal.aborted && visit.current === event)
          setIssue('This visit could not be saved to your history.')
      })
    return () => controller.abort()
  }, [owner, enabled, movie?.id, auth.csrf, retries])
  return {
    issue: enabled ? issue : '',
    retry: () => setRetries((count) => count + 1),
  }
}
