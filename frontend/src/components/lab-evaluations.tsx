import { AlertTriangle, CheckCircle2, Info, MinusCircle } from 'lucide-react'
import type {
  LabEvidenceCategory,
  LabFeature,
  LabMetric,
  LabSuite,
} from '../lib/lab-contracts'

type FeatureFilter = LabFeature | 'all'
type CategoryFilter = LabEvidenceCategory | 'all'

const featureLabels: Record<LabFeature, string> = {
  search: 'Search',
  facts: 'Facts',
  quiz: 'Quiz',
  discuss: 'Discuss',
  retrieval: 'Retrieval',
  readiness: 'Readiness',
}
const categoryLabels: Record<LabEvidenceCategory, string> = {
  development: 'Development',
  held_out: 'Held-out',
  smoke: 'Smoke',
  live: 'Live',
  publication: 'Publication',
  audit: 'Audit',
}

function MetricValue({ metric }: { metric: LabMetric }) {
  const display =
    metric.unit === 'percent'
      ? `${metric.value}%`
      : metric.unit === 'seconds'
        ? `${metric.value}s`
        : metric.value
  return (
    <div className="lab-metric">
      <span>{metric.label}</span>
      <strong>{display}</strong>
      {metric.numerator !== null && metric.denominator !== null && (
        <small>
          {metric.numerator} / {metric.denominator} cases
        </small>
      )}
      <p>{metric.definition}</p>
    </div>
  )
}

function SuiteIcon({ status }: { status: LabSuite['status'] }) {
  if (status === 'pass') return <CheckCircle2 size={18} aria-hidden="true" />
  if (status === 'attention' || status === 'error')
    return <AlertTriangle size={18} aria-hidden="true" />
  if (status === 'informational') return <Info size={18} aria-hidden="true" />
  return <MinusCircle size={18} aria-hidden="true" />
}

export function LabEvaluations({
  suites,
  feature,
  category,
  onFeatureChange,
  onCategoryChange,
}: {
  suites: LabSuite[]
  feature: FeatureFilter
  category: CategoryFilter
  onFeatureChange: (value: FeatureFilter) => void
  onCategoryChange: (value: CategoryFilter) => void
}) {
  const filtered = suites.filter(
    (suite) =>
      (feature === 'all' || suite.feature === feature) &&
      (category === 'all' || suite.category === category),
  )
  return (
    <section className="lab-section" aria-labelledby="lab-evaluations-title">
      <div className="lab-section-heading lab-section-heading--filters">
        <div>
          <p className="eyebrow">EVALUATION RESULTS</p>
          <h2 id="lab-evaluations-title">Measured evidence</h2>
        </div>
        <div className="lab-filters">
          <label>
            Feature
            <select
              value={feature}
              onChange={(event) =>
                onFeatureChange(event.target.value as FeatureFilter)
              }
            >
              <option value="all">All features</option>
              {Object.entries(featureLabels).map(([value, label]) => (
                <option value={value} key={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Evidence category
            <select
              value={category}
              onChange={(event) =>
                onCategoryChange(event.target.value as CategoryFilter)
              }
            >
              <option value="all">All evidence</option>
              {Object.entries(categoryLabels).map(([value, label]) => (
                <option value={value} key={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>
      {filtered.length === 0 ? (
        <div className="lab-empty">
          <h3>No evaluation matches these filters.</h3>
          <p>Choose another feature or evidence category.</p>
        </div>
      ) : (
        <div className="lab-suite-list">
          {filtered.map((suite) => (
            <article className="lab-suite" key={suite.id}>
              <div className="lab-suite__header">
                <div>
                  <div className="lab-suite__labels">
                    <span>{featureLabels[suite.feature]}</span>
                    <span>{categoryLabels[suite.category]}</span>
                    {suite.gated && <span>Gated</span>}
                  </div>
                  <h3>{suite.title}</h3>
                </div>
                <span className={`lab-status lab-status--${suite.status}`}>
                  <SuiteIcon status={suite.status} />
                  {suite.status.replace('_', ' ')}
                </span>
              </div>
              {suite.metrics.length > 0 ? (
                <div className="lab-metric-grid">
                  {suite.metrics.map((metric) => (
                    <MetricValue metric={metric} key={metric.id} />
                  ))}
                </div>
              ) : (
                <p className="lab-suite__empty">No valid metrics available.</p>
              )}
              {suite.warnings.map((warning) => (
                <p className="lab-inline-warning" key={warning.message}>
                  <AlertTriangle size={16} aria-hidden="true" />
                  {warning.message}
                </p>
              ))}
              <div className="lab-suite__notes">
                <p>
                  <strong>Source report</strong>
                  <code>{suite.source_label}</code>
                </p>
                {suite.limitations.map((limitation) => (
                  <p key={limitation}>{limitation}</p>
                ))}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
