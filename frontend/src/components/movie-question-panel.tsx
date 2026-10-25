import { useAuth } from '../lib/auth'
import { useEffect, useRef, useState } from 'react'
import { askMovie } from '../lib/api'
import type { MovieAnswer } from '../lib/contracts'
import { Button } from './ui/button'

export function MovieQuestionPanel({
  movieId,
  movieTitle,
  available,
  allowSpoilers,
}: {
  movieId: number
  movieTitle: string
  available: boolean
  allowSpoilers: boolean
}) {
  const auth = useAuth()
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<MovieAnswer | null>(null)
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const controller = useRef<AbortController | null>(null)
  useEffect(() => () => controller.current?.abort(), [])

  if (!available)
    return (
      <section className="question-panel">
        <p className="eyebrow">A CONVERSATION WITH SOURCES</p>
        <h2>A little more to discover.</h2>
        <p>A reviewed discussion source is not available for this film yet.</p>
      </section>
    )

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!allowSpoilers || !question.trim() || pending) return
    const active = new AbortController()
    controller.current = active
    setPending(true)
    setError('')
    setAnswer(null)
    try {
      const result = await askMovie(
        movieId,
        question.trim(),
        allowSpoilers,
        active.signal,
        auth.csrf,
      )
      if (!active.signal.aborted) setAnswer(result)
    } catch (problem) {
      if (!active.signal.aborted)
        setError(
          problem instanceof Error ? problem.message : 'Please try again.',
        )
    } finally {
      if (!active.signal.aborted) setPending(false)
    }
  }

  function cancel(event: React.MouseEvent<HTMLButtonElement>) {
    // Prevent this click submitting after React replaces Cancel with Ask.
    event.preventDefault()
    controller.current?.abort()
    setPending(false)
    setError('The answer request was cancelled. You can ask again.')
  }

  return (
    <section className="question-panel" aria-labelledby="question-heading">
      <header className="feature-heading">
        <div>
          <p className="eyebrow">A CONVERSATION WITH SOURCES</p>
          <h2 id="question-heading">Go a little deeper.</h2>
          <p>Explore the film with answers grounded in evidence.</p>
        </div>
      </header>
      <p className="question-source-note">
        Plot sources ground the answers. Available scripts add scene context.
      </p>
      {!allowSpoilers && (
        <p className="question-permission" role="status">
          Allow spoilers using your preference above to ask a question. This
          source hasn’t been classified as spoiler-free.
        </p>
      )}
      <div className="question-suggestions" aria-label="Example questions">
        {(movieId === 157336
          ? [
              'Who composed the music for Interstellar?',
              'Which instrument was chosen as the primary instrument for the score?',
            ]
          : [`Who directed ${movieTitle}?`, `How was ${movieTitle} filmed?`]
        ).map((example) => (
          <button
            type="button"
            key={example}
            disabled={!allowSpoilers || pending}
            onClick={() => setQuestion(example)}
          >
            {example}
          </button>
        ))}
      </div>
      <form onSubmit={submit} aria-busy={pending}>
        <label htmlFor="movie-question">Your question</label>
        <textarea
          id="movie-question"
          rows={3}
          maxLength={1000}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          disabled={!allowSpoilers || pending}
          placeholder="Ask about a scene, character, or theme."
          aria-describedby="question-help"
        />
        <div className="question-actions">
          <p id="question-help">
            Answers depend on available evidence. Preparing the first source can
            take a few minutes.
          </p>
          {pending ? (
            <Button type="button" variant="outline" onClick={cancel}>
              Cancel request
            </Button>
          ) : (
            <Button type="submit" disabled={!allowSpoilers || !question.trim()}>
              Ask PlotSpot{' '}
            </Button>
          )}
        </div>
      </form>
      {pending && (
        <p role="status">Finding evidence and preparing your answer…</p>
      )}
      {error && (
        <p className="question-error" role="alert">
          {error}
        </p>
      )}
      {answer && (
        <div className="question-answer" role="status" aria-live="polite">
          <p className="eyebrow">
            {answer.status === 'answered'
              ? 'AN ANSWER WITH EVIDENCE'
              : 'A NOTE ON THE EVIDENCE'}
          </p>
          <p className="answer-copy">{answer.answer}</p>
          {answer.source_coverage?.degraded && (
            <p className="browser-note">
              Some web sources could not be verified. This response uses the
              available cited evidence.
            </p>
          )}
          {answer.answer_kind === 'interpretation' && (
            <p className="browser-note">
              A possible interpretation, not a scored answer.
            </p>
          )}
          {answer.script_context && (
            <details className="question-citations">
              <summary>Script context</summary>
              <p className="browser-note">
                {answer.script_context.version}. Draft details can differ from
                the film.
              </p>
              <a
                className="text-link"
                href={answer.script_context.source_ref}
                target="_blank"
                rel="noopener noreferrer"
              >
                Read the script
              </a>
            </details>
          )}
          {answer.citations.length > 0 && (
            <div className="question-citations">
              <h3>Read the evidence</h3>
              {answer.citations.map((citation, index) => (
                <details key={citation.passage_id}>
                  <summary>
                    Source {index + 1} · {citation.source_label}
                  </summary>
                  <blockquote>{citation.excerpt}</blockquote>
                  <a
                    className="text-link"
                    href={citation.source_ref}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Read this source revision{' '}
                  </a>
                </details>
              ))}
              {answer.citations.some((c) =>
                c.source_ref.startsWith('https://en.wikipedia.org/'),
              ) && (
                <p className="browser-note">
                  Source text: Wikipedia contributors.{' '}
                  <a
                    href="https://en.wikipedia.org/wiki/Wikipedia:Copyrights"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Attribution and reuse terms
                  </a>
                  .
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  )
}
