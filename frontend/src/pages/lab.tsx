import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, FlaskConical, RotateCcw } from 'lucide-react'
import { LabEvaluations } from '../components/lab-evaluations'
import { LabRuns } from '../components/lab-runs'
import { LabSummary } from '../components/lab-summary'
import { Button } from '../components/ui/button'
import { getLabOverview, getLabRun, getLabRuns } from '../lib/lab-api'
import type {
  LabEvidenceCategory,
  LabFeature,
  LabRunState,
  LabWorkflow,
} from '../lib/lab-contracts'

export function LabPage() {
  const [feature, setFeature] = useState<LabFeature | 'all'>('all')
  const [category, setCategory] = useState<LabEvidenceCategory | 'all'>('all')
  const [workflow, setWorkflow] = useState<LabWorkflow | 'all'>('all')
  const [runState, setRunState] = useState<LabRunState | 'all'>('all')
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const overview = useQuery({
    queryKey: ['lab', 'overview'],
    queryFn: ({ signal }) => getLabOverview(signal),
    staleTime: 30_000,
  })
  const runs = useQuery({
    queryKey: ['lab', 'runs', workflow, runState],
    queryFn: ({ signal }) =>
      getLabRuns(
        {
          workflow: workflow === 'all' ? undefined : workflow,
          state: runState === 'all' ? undefined : runState,
          limit: 20,
        },
        signal,
      ),
    staleTime: 15_000,
  })
  const detail = useQuery({
    queryKey: ['lab', 'run', selectedRunId],
    queryFn: ({ signal }) => getLabRun(selectedRunId!, signal),
    enabled: selectedRunId !== null,
  })
  if (overview.isPending) {
    return (
      <div className="page-width lab-page lab-page--loading" role="status">
        <FlaskConical size={28} aria-hidden="true" />
        <p>Loading reliability evidence…</p>
      </div>
    )
  }
  if (overview.isError) {
    return (
      <div className="page-width lab-page">
        <div className="status-panel" role="alert">
          <AlertTriangle size={28} aria-hidden="true" />
          <h1>Reliability data is unavailable</h1>
          <p>
            Check that the local lab is enabled in both the backend and
            frontend, then try again.
          </p>
          <Button onClick={() => void overview.refetch()}>
            <RotateCcw size={16} aria-hidden="true" /> Try again
          </Button>
        </div>
      </div>
    )
  }
  const data = overview.data
  return (
    <div className="page-width lab-page">
      <header className="lab-hero">
        <div>
          <div className="lab-hero__labels">
            <span>Development only</span>
            <span className={`lab-status lab-status--${data.status}`}>
              {data.status.replace('_', ' ')}
            </span>
          </div>
          <h1>AI Reliability Lab</h1>
          <p>
            Inspect retrieval, generation, verification and evaluation quality
            from safe local evidence.
          </p>
        </div>
        <p className="lab-hero__updated">
          Snapshot{' '}
          <time dateTime={data.generated_at}>
            {new Intl.DateTimeFormat(undefined, {
              dateStyle: 'medium',
              timeStyle: 'short',
            }).format(new Date(data.generated_at))}
          </time>
        </p>
      </header>

      {data.warnings.length > 0 && (
        <aside className="lab-notice" role="status">
          <AlertTriangle size={20} aria-hidden="true" />
          <div>
            <strong>Some evidence is unavailable</strong>
            <p>{data.warnings.map((warning) => warning.message).join(' ')}</p>
          </div>
        </aside>
      )}

      <LabSummary overview={data} />
      <LabEvaluations
        suites={data.suites}
        feature={feature}
        category={category}
        onFeatureChange={setFeature}
        onCategoryChange={setCategory}
      />
      {runs.isError ? (
        <section className="lab-section lab-empty" role="alert">
          <h2>Recent runs are unavailable.</h2>
          <p>The stored evaluation results above are still usable.</p>
        </section>
      ) : (
        <LabRuns
          runs={runs.data?.items ?? []}
          selectedId={selectedRunId}
          detail={detail.data}
          detailLoading={detail.isPending && selectedRunId !== null}
          detailError={detail.isError}
          workflow={workflow}
          state={runState}
          onWorkflowChange={(value) => {
            setWorkflow(value)
            setSelectedRunId(null)
          }}
          onStateChange={(value) => {
            setRunState(value)
            setSelectedRunId(null)
          }}
          onSelect={(value) =>
            setSelectedRunId((current) => (current === value ? null : value))
          }
        />
      )}

      <section
        className="lab-section lab-limitations"
        aria-labelledby="lab-limitations-title"
      >
        <p className="eyebrow">READ THE LIMITS</p>
        <h2 id="lab-limitations-title">What this evidence can establish</h2>
        <ul>
          {data.limitations.map((limitation) => (
            <li key={limitation}>{limitation}</li>
          ))}
        </ul>
      </section>
    </div>
  )
}
