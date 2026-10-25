import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  DatabaseZap,
  ShieldCheck,
} from 'lucide-react'
import type { LabOverview } from '../lib/lab-contracts'

const labels = {
  search: 'Search',
  facts: 'Facts',
  quiz: 'Quiz',
  discuss: 'Discuss',
  retrieval: 'Retrieval',
  generation: 'Generation',
  verification: 'Verification',
  publication: 'Publication',
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'healthy') return <CheckCircle2 size={17} aria-hidden="true" />
  if (status === 'attention')
    return <AlertTriangle size={17} aria-hidden="true" />
  return <CircleDashed size={17} aria-hidden="true" />
}

export function LabSummary({ overview }: { overview: LabOverview }) {
  const cards = [
    {
      label: 'Evaluation gates',
      value: `${overview.gated_passed} of ${overview.gated_total}`,
      detail: `${overview.gated_passed} of ${overview.gated_total} gated suites passing`,
      icon: ShieldCheck,
    },
    {
      label: 'Held-out checks',
      value:
        overview.held_out_total > 0
          ? `${overview.held_out_passed} / ${overview.held_out_total}`
          : 'No gate',
      detail: 'Recorded cases across the registered held-out reports',
      icon: DatabaseZap,
    },
    {
      label: 'Recent successful runs',
      value: String(overview.recent_successful_runs),
      detail: 'Completed local records in the bounded recent window',
      icon: Activity,
    },
    {
      label: 'Degraded or failed',
      value: String(overview.degraded_or_failed_runs),
      detail: 'Recent records requiring attention',
      icon: AlertTriangle,
    },
  ]
  return (
    <>
      <section className="lab-section" aria-labelledby="lab-snapshot-title">
        <div className="lab-section-heading">
          <div>
            <p className="eyebrow">CURRENT SNAPSHOT</p>
            <h2 id="lab-snapshot-title">Quality at a glance</h2>
          </div>
          <p>Rates retain their original sample size.</p>
        </div>
        <div className="lab-summary-grid">
          {cards.map(({ label, value, detail, icon: Icon }) => (
            <article className="lab-summary-card" key={label}>
              <div className="lab-summary-card__top">
                <span>{label}</span>
                <Icon size={20} aria-hidden="true" />
              </div>
              <strong>{value}</strong>
              <p>{detail}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="lab-section" aria-labelledby="lab-health-title">
        <div className="lab-section-heading">
          <div>
            <p className="eyebrow">PIPELINE HEALTH</p>
            <h2 id="lab-health-title">Evidence by stage</h2>
          </div>
          <p>Informational measurements remain ungraded.</p>
        </div>
        <div className="lab-health-list">
          {overview.features.map((feature) => (
            <article className="lab-health-row" key={feature.feature}>
              <div className="lab-health-feature">
                <strong>{labels[feature.feature]}</strong>
                <span className={`lab-status lab-status--${feature.status}`}>
                  <StatusIcon status={feature.status} />
                  {feature.status.replace('_', ' ')}
                </span>
              </div>
              <ul aria-label={`${labels[feature.feature]} pipeline stages`}>
                {feature.stages.map((stage) => (
                  <li
                    className={`lab-stage lab-stage--${stage.status}`}
                    key={stage.stage}
                    title={stage.detail}
                  >
                    <StatusIcon status={stage.status} />
                    <span>{labels[stage.stage]}</span>
                    <small>{stage.status.replace('_', ' ')}</small>
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </section>
    </>
  )
}
