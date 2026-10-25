import { useQuizHistory } from '../lib/use-quiz-history'
import { useAuth } from '../lib/auth'
import { useEffect, useRef, useState } from 'react'
import { Sparkles, Check, X } from 'lucide-react'
import { buildMovieQuiz, generateMoreQuiz } from '../lib/api'
import type { MovieQuiz } from '../lib/contracts'
import { Button } from './ui/button'

export function MovieQuizPanel({
  movieId,
  available,
  allowSpoilers,
}: {
  movieId: number
  available: boolean
  allowSpoilers: boolean
}) {
  const auth = useAuth()
  const [quiz, setQuiz] = useState<MovieQuiz | null>(null)
  const [choices, setChoices] = useState<Record<string, number>>({})
  const history = useQuizHistory(quiz, movieId, choices)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [generating, setGenerating] = useState(false)
  const [generationMessage, setGenerationMessage] = useState('')
  const controller = useRef<AbortController | null>(null)
  useEffect(() => {
    if (allowSpoilers && available) void build()
    return () => controller.current?.abort()
  }, [movieId, allowSpoilers, available])

  async function build() {
    if (pending || !allowSpoilers) return
    const active = new AbortController()
    controller.current = active
    setPending(true)
    setError('')
    setQuiz(null)
    setChoices({})
    try {
      const result = await buildMovieQuiz(movieId, allowSpoilers, active.signal)
      if (!active.signal.aborted) setQuiz(result)
    } catch (problem) {
      if (!active.signal.aborted)
        setError(
          problem instanceof Error ? problem.message : 'Please try again.',
        )
    } finally {
      if (!active.signal.aborted) setPending(false)
    }
  }

  async function more() {
    if (generating || !allowSpoilers) return
    const active = new AbortController()
    controller.current = active
    setGenerating(true)
    setGenerationMessage('')
    try {
      const result = await generateMoreQuiz(movieId, active.signal, auth.csrf)
      if (!active.signal.aborted) {
        if (
          result.content_version !== quiz?.content_version ||
          result.items.length !== quiz?.items.length
        )
          history.newRound()
        setQuiz(result)
        setGenerationMessage(result.message)
      }
    } catch (problem) {
      if (!active.signal.aborted)
        setGenerationMessage(
          problem instanceof Error ? problem.message : 'Please try again.',
        )
    } finally {
      if (!active.signal.aborted) setGenerating(false)
    }
  }

  const answered = Object.keys(choices).length
  const scored =
    quiz?.items.filter((item) => item.kind !== 'interpretation') ?? []
  const score = scored.filter(
    (item) => choices[item.id] === item.correct_index,
  ).length
  return (
    <section
      className="question-panel quiz-panel"
      aria-labelledby="quiz-heading"
    >
      <header className="feature-heading">
        <div>
          <p className="eyebrow">THE STORY QUIZ</p>
          <h2 id="quiz-heading">Test your recall.</h2>
          <p>Plot twists, pivotal choices, and the ending.</p>
        </div>
        <span className="feature-badge">
          {available ? `${scored.length || 10} questions` : 'Not available yet'}
        </span>
      </header>
      {!available ? (
        <p>A quiz has not been prepared for this film yet.</p>
      ) : (
        <>
          {!allowSpoilers && (
            <p role="status" className="question-permission">
              Allow spoilers using your preference above to start the quiz.
            </p>
          )}
          {!quiz && allowSpoilers && (
            <div className="question-actions">
              <Button
                type="button"
                disabled={!allowSpoilers || pending}
                onClick={() => void build()}
              >
                {pending ? 'Loading saved quiz…' : 'Retry loading quiz'}
              </Button>
              {pending && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    controller.current?.abort()
                    setPending(false)
                    setError('Quiz loading was cancelled. You can try again.')
                  }}
                >
                  Cancel quiz
                </Button>
              )}
            </div>
          )}
          {pending && <p role="status">Loading your saved story collection…</p>}
          {error && (
            <p role="alert" className="question-error">
              {error}
            </p>
          )}
          {quiz && (
            <>
              {quiz.status !== 'ready' ? (
                <p role="status">{quiz.message}</p>
              ) : (
                <>
                  <div className="quiz-score" role="status">
                    <span>
                      {answered === quiz.items.length
                        ? 'ROUND COMPLETE'
                        : `${answered} ANSWERED`}
                    </span>
                    <strong>
                      {score} / {scored.length}
                    </strong>
                  </div>
                  {history.status !== 'idle' && (
                    <div className="quiz-history-feedback">
                      <p role={history.status === 'error' ? 'alert' : 'status'}>
                        {history.status === 'saving'
                          ? 'Saving round to your history…'
                          : history.status === 'saved'
                            ? 'Round saved to quiz history'
                            : history.issue}
                      </p>
                      {history.status === 'error' && (
                        <Button variant="ghost" onClick={history.retry}>
                          Retry saving round
                        </Button>
                      )}
                    </div>
                  )}
                  {scored.length < 10 && <p>{quiz.message}</p>}
                  <div className="story-question-grid">
                    {quiz.items.map((item, index) => {
                      const picked = choices[item.id]
                      const revealed = picked !== undefined
                      const reflection = item.kind === 'interpretation'
                      return (
                        <article
                          className="quiz-card"
                          key={item.id}
                          aria-labelledby={`quiz-${item.id}`}
                        >
                          <p className="eyebrow">
                            {reflection
                              ? 'REFLECTION · UNSCORED'
                              : `${String(index + 1).padStart(2, '0')} / ${scored.length} · ${item.kind === 'ending' ? 'ENDING' : 'STORY'}`}
                          </p>
                          <h3 id={`quiz-${item.id}`}>{item.question}</h3>
                          <div
                            className="quiz-options"
                            role="group"
                            aria-label={`Answers to question ${index + 1}`}
                          >
                            {item.options.map((option, optionIndex) => (
                              <button
                                type="button"
                                key={option}
                                disabled={revealed}
                                className={`quiz-option ${revealed && optionIndex === (reflection ? picked : item.correct_index) ? 'quiz-correct' : ''} ${!reflection && revealed && optionIndex === picked && picked !== item.correct_index ? 'quiz-incorrect' : ''}`}
                                onClick={() =>
                                  setChoices((previous) => ({
                                    ...previous,
                                    [item.id]: optionIndex,
                                  }))
                                }
                              >
                                <span className="quiz-letter">
                                  {String.fromCharCode(65 + optionIndex)}
                                </span>
                                <span>{option}</span>
                                {revealed &&
                                  !reflection &&
                                  optionIndex === item.correct_index && (
                                    <span className="quiz-option-note">
                                      Correct answer
                                    </span>
                                  )}
                                {revealed &&
                                  optionIndex === picked &&
                                  (reflection ||
                                    picked !== item.correct_index) && (
                                    <span className="quiz-option-note">
                                      Your choice
                                    </span>
                                  )}
                              </button>
                            ))}
                          </div>
                          {revealed && (
                            <div className="quiz-explanation" role="status">
                              <strong className="answer-feedback">
                                {!reflection &&
                                  (picked === item.correct_index ? (
                                    <Check size={18} aria-hidden="true" />
                                  ) : (
                                    <X size={18} aria-hidden="true" />
                                  ))}
                                {reflection
                                  ? 'One possible reading'
                                  : picked === item.correct_index
                                    ? 'Correct'
                                    : `Correct answer: Option ${String.fromCharCode(65 + item.correct_index)}, ${item.options[item.correct_index]}`}
                              </strong>
                              <p>{item.explanation}</p>
                              {(reflection ||
                                picked !== item.correct_index) && (
                                <div className="question-citations">
                                  {item.citations.map((citation) => (
                                    <details key={citation.passage_id}>
                                      <summary>Why this answer?</summary>
                                      <blockquote>
                                        {citation.excerpt}
                                      </blockquote>
                                      <a
                                        className="text-link"
                                        href={citation.source_ref}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                      >
                                        View source{' '}
                                      </a>
                                    </details>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}
                        </article>
                      )
                    })}
                  </div>
                  <div className="quiz-bottom">
                    <div>
                      <h3>
                        {quiz.can_generate_more
                          ? 'Keep the questions coming.'
                          : 'Your story round.'}
                      </h3>
                      <p>
                        {quiz.can_generate_more
                          ? 'Add new story questions to your quiz.'
                          : 'No additional questions are available for this collection yet.'}
                      </p>
                    </div>
                    <div className="quiz-bottom-actions">
                      {answered === quiz.items.length && (
                        <Button
                          type="button"
                          variant="outline"
                          disabled={history.status === 'saving'}
                          onClick={() => {
                            history.newRound()
                            setChoices({})
                          }}
                        >
                          Play again
                        </Button>
                      )}
                      <Button
                        type="button"
                        disabled={
                          generating ||
                          history.status === 'saving' ||
                          !quiz.can_generate_more
                        }
                        onClick={() => void more()}
                      >
                        <Sparkles size={17} aria-hidden="true" />
                        {generating
                          ? 'Generating questions…'
                          : !quiz.can_generate_more
                            ? 'More questions unavailable'
                            : 'Generate more questions'}
                      </Button>
                    </div>
                  </div>
                  {generating && (
                    <p role="status" className="generation-note">
                      Checking new questions against the story. This may take a
                      moment.
                    </p>
                  )}
                  {generationMessage && (
                    <p role="status" className="generation-note">
                      {generationMessage}
                    </p>
                  )}
                  <p className="feature-credit">
                    Sources:{' '}
                    {Array.from(
                      new Set(
                        quiz.items.flatMap((item) =>
                          item.citations.map((c) =>
                            new URL(c.source_ref).hostname ===
                            'en.wikipedia.org'
                              ? 'Wikipedia'
                              : new URL(c.source_ref).hostname,
                          ),
                        ),
                      ),
                    ).join(', ')}{' '}
                    {quiz.items.some((item) =>
                      item.citations.some(
                        (c) =>
                          new URL(c.source_ref).hostname === 'en.wikipedia.org',
                      ),
                    ) && (
                      <>
                        {' '}
                        ·{' '}
                        <a
                          href="https://en.wikipedia.org/wiki/Wikipedia:Copyrights"
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          Attribution
                        </a>
                      </>
                    )}
                  </p>
                </>
              )}
            </>
          )}
        </>
      )}
    </section>
  )
}
