import { useEffect, useRef, useState } from 'react'
import { useAuth } from './auth'
import { recordQuiz } from './history-api'
import type { MovieQuiz } from './contracts'

export function useQuizHistory(
  quiz: MovieQuiz | null,
  movieId: number,
  choices: Record<string, number>,
) {
  const auth = useAuth()
  const owner = auth.user?.id
  const [round, setRound] = useState(() => crypto.randomUUID())
  const [retry, setRetry] = useState(0)
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>(
    'idle',
  )
  const [issue, setIssue] = useState('')
  const completed =
    !!quiz &&
    quiz.status === 'ready' &&
    quiz.items.length > 0 &&
    quiz.items.every((q) => choices[q.id] !== undefined)
  const saved = useRef(new Set<string>())
  useEffect(() => {
    if (!completed || !owner || auth.status !== 'authenticated' || !quiz) return
    if (saved.current.has(round)) return
    if (!quiz.content_version || !quiz.prepared_at) {
      setStatus('error')
      setIssue('This quiz needs to be reloaded before the round can be saved.')
      return
    }
    const controller = new AbortController()
    setStatus('saving')
    setIssue('')
    const answers = Object.fromEntries(
      quiz.items.map((q) => [q.id, choices[q.id]]),
    )
    void recordQuiz(
      owner,
      movieId,
      round,
      quiz.content_version,
      quiz.prepared_at,
      answers,
      auth.csrf,
      controller.signal,
    )
      .then(() => {
        if (!controller.signal.aborted) {
          saved.current.add(round)
          setStatus('saved')
        }
      })
      .catch((problem) => {
        if (!controller.signal.aborted) {
          setStatus('error')
          setIssue(
            problem instanceof Error
              ? problem.message
              : 'This round could not be saved. Try again.',
          )
        }
      })
    return () => controller.abort()
  }, [
    completed,
    owner,
    auth.status,
    auth.csrf,
    quiz,
    choices,
    movieId,
    round,
    retry,
  ])
  return {
    status: completed ? status : 'idle',
    issue,
    retry: () => setRetry((n) => n + 1),
    newRound: () => {
      setRound(crypto.randomUUID())
      setStatus('idle')
      setIssue('')
    },
  }
}
