import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  CircleDashed,
  Clock3,
} from 'lucide-react'
import type {
  LabRunDetail,
  LabRunState,
  LabRunSummary,
  LabWorkflow,
} from '../lib/lab-contracts'

type WorkflowFilter = LabWorkflow | 'all'
type StateFilter = LabRunState | 'all'

const workflowLabels = {
  preparation: 'Content preparation',
  story_rag: 'Story RAG',
}

function stageLabel(value: string) {
  const labels: Record<string, string> = {
    source: 'Source',
    index: 'Index',
    retrieve: 'Retrieve',
    retrieving: 'Retrieve',
    generate: 'Generate',
    generating: 'Generate',
    verify: 'Verify',
    reviewing: 'Review',
    finished: 'Finish',
  }
  return labels[value] ?? value
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function StageIcon({ status }: { status: string }) {
  if (status === 'completed')
    return <CheckCircle2 size={18} aria-hidden="true" />
  if (status === 'attention')
    return <AlertTriangle size={18} aria-hidden="true" />
  return <CircleDashed size={18} aria-hidden="true" />
}

export function LabRuns({
  runs,
  selectedId,
  detail,
  detailLoading,
  detailError,
  workflow,
  state,
  onWorkflowChange,
  onStateChange,
  onSelect,
}: {
  runs: LabRunSummary[]
  selectedId: string | null
  detail?: LabRunDetail
  detailLoading: boolean
  detailError: boolean
  workflow: WorkflowFilter
  state: StateFilter
  onWorkflowChange: (value: WorkflowFilter) => void
  onStateChange: (value: StateFilter) => void
  onSelect: (value: string) => void
}) {
  return (
    <section className="lab-section" aria-labelledby="lab-runs-title">
      <div className="lab-section-heading lab-section-heading--filters">
        <div>
          <p className="eyebrow">RECENT RUNS</p>
          <h2 id="lab-runs-title">Recorded pipeline activity</h2>
        </div>
        <div className="lab-filters">
          <label>
            Workflow
            <select
              value={workflow}
              onChange={(event) =>
                onWorkflowChange(event.target.value as WorkflowFilter)
              }
            >
              <option value="all">All workflows</option>
              <option value="story_rag">Story RAG</option>
              <option value="preparation">Content preparation</option>
            </select>
          </label>
          <label>
            Run status
            <select
              value={state}
              onChange={(event) =>
                onStateChange(event.target.value as StateFilter)
              }
            >
              <option value="all">All statuses</option>
              <option value="completed">Completed</option>
              <option value="needs_review">Needs review</option>
              <option value="published">Published</option>
              <option value="running">Running</option>
              <option value="failed">Failed</option>
              <option value="interrupted">Interrupted</option>
            </select>
          </label>
        </div>
      </div>
      {runs.length === 0 ? (
        <div className="lab-empty">
          <h3>No recorded runs match these filters.</h3>
          <p>Run records appear after a local preparation or story workflow.</p>
        </div>
      ) : (
        <div className="lab-runs-layout">
          <div className="lab-run-list" role="list">
            {runs.map((run) => {
              const expanded = selectedId === run.id
              return (
                <button
                  type="button"
                  className="lab-run"
                  key={run.id}
                  aria-expanded={expanded}
                  aria-controls="lab-run-detail"
                  aria-label={`${run.title ?? `Movie ${run.movie_id}`} · ${workflowLabels[run.workflow]} · ${run.state.replace('_', ' ')}`}
                  onClick={() => onSelect(run.id)}
                >
                  <span className="lab-run__main">
                    <strong>{run.title ?? `Movie ${run.movie_id}`}</strong>
                    <small>{workflowLabels[run.workflow]}</small>
                  </span>
                  <span className="lab-run__counts">
                    {run.source_count} sources · {run.retrieval_count} retrieved
                  </span>
                  <span className={`lab-status lab-status--${run.state}`}>
                    {run.degraded && (
                      <AlertTriangle size={15} aria-hidden="true" />
                    )}
                    {run.state.replace('_', ' ')}
                  </span>
                  <time dateTime={run.updated_at}>
                    {formatTime(run.updated_at)}
                  </time>
                  <ChevronDown
                    size={18}
                    aria-hidden="true"
                    className={expanded ? 'is-open' : ''}
                  />
                </button>
              )
            })}
          </div>
          {selectedId && (
            <div
              id="lab-run-detail"
              className="lab-run-detail"
              aria-live="polite"
            >
              {detailLoading && <p>Loading the sanitized run timeline…</p>}
              {detailError && (
                <p className="lab-inline-warning">
                  <AlertTriangle size={16} aria-hidden="true" />
                  This run detail is unavailable.
                </p>
              )}
              {detail && (
                <>
                  <div className="lab-run-detail__heading">
                    <div>
                      <p className="eyebrow">SANITIZED TRACE</p>
                      <h3>Run timeline</h3>
                    </div>
                    <span>{workflowLabels[detail.workflow]}</span>
                  </div>
                  <ol className="lab-timeline">
                    {detail.stages.map((stage, index) => (
                      <li key={`${stage.name}-${index}`}>
                        <span
                          className={`lab-timeline__icon lab-timeline__icon--${stage.status}`}
                        >
                          <StageIcon status={stage.status} />
                        </span>
                        <div>
                          <div className="lab-timeline__title">
                            <strong>{stageLabel(stage.name)}</strong>
                            <span>{stage.status}</span>
                          </div>
                          <p>{stage.message}</p>
                          <small>
                            {stage.count !== null && `${stage.count} records`}
                            {stage.count !== null &&
                              stage.duration_seconds !== null &&
                              ' · '}
                            {stage.duration_seconds !== null && (
                              <>
                                <Clock3 size={13} aria-hidden="true" />
                                {stage.duration_seconds}s
                              </>
                            )}
                          </small>
                        </div>
                      </li>
                    ))}
                  </ol>
                  <p className="lab-run-detail__privacy">
                    Prompts, user questions, source passages, drafts and model
                    reasoning are excluded from this view.
                  </p>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  )
}
