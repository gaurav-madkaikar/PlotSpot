import { z } from 'zod'

export const labWarningSchema = z
  .object({
    code: z.enum(['missing_source', 'invalid_source', 'unsupported_source']),
    suite_id: z.string().max(60).nullable(),
    message: z.string().min(1).max(240),
  })
  .strict()

export const labMetricSchema = z
  .object({
    id: z.string().regex(/^[a-z0-9_]{1,50}$/),
    label: z.string().min(1).max(100),
    value: z.union([z.number().finite(), z.string().max(100)]),
    unit: z.enum(['count', 'percent', 'seconds', 'ratio', 'text']),
    numerator: z.number().int().nonnegative().nullable(),
    denominator: z.number().int().positive().nullable(),
    direction: z.enum(['higher', 'lower', 'neutral']),
    definition: z.string().min(1).max(300),
  })
  .strict()
  .superRefine((metric, context) => {
    if (
      metric.unit === 'percent' &&
      (metric.numerator === null || metric.denominator === null)
    )
      context.addIssue({
        code: 'custom',
        message: 'Percent metrics require numerator and denominator',
      })
  })

const featureSchema = z.enum([
  'search',
  'facts',
  'quiz',
  'discuss',
  'retrieval',
  'readiness',
])
const evidenceCategorySchema = z.enum([
  'development',
  'held_out',
  'smoke',
  'live',
  'publication',
  'audit',
])
const suiteStatusSchema = z.enum([
  'pass',
  'attention',
  'informational',
  'error',
  'no_data',
])

export const labSuiteSchema = z
  .object({
    id: z.string().regex(/^[a-z0-9_]{1,60}$/),
    title: z.string().min(1).max(120),
    feature: featureSchema,
    category: evidenceCategorySchema,
    status: suiteStatusSchema,
    gated: z.boolean(),
    recorded_at: z.string().datetime({ offset: true }).nullable(),
    metrics: z.array(labMetricSchema).max(30),
    source_label: z.string().min(1).max(160),
    limitations: z.array(z.string().min(1).max(500)).max(12),
    warnings: z.array(labWarningSchema).max(12),
  })
  .strict()

export const pipelineStageHealthSchema = z
  .object({
    stage: z.enum(['retrieval', 'generation', 'verification', 'publication']),
    status: z.enum(['healthy', 'attention', 'no_data', 'not_applicable']),
    detail: z.string().min(1).max(180),
  })
  .strict()

export const featureHealthSchema = z
  .object({
    feature: z.enum(['search', 'facts', 'quiz', 'discuss']),
    status: z.enum(['healthy', 'attention', 'partial', 'no_data']),
    stages: z.array(pipelineStageHealthSchema).min(1).max(4),
  })
  .strict()

const runStateSchema = z.enum([
  'queued',
  'running',
  'completed',
  'needs_review',
  'incomplete',
  'ready',
  'published',
  'failed',
  'cancelled',
  'interrupted',
])
const workflowSchema = z.enum(['preparation', 'story_rag'])

export const labRunSummarySchema = z
  .object({
    id: z.string().regex(/^(?:prep|story)_[a-f0-9]{32}$/),
    movie_id: z.number().int().positive(),
    title: z.string().max(200).nullable(),
    workflow: workflowSchema,
    state: runStateSchema,
    updated_at: z.string().datetime({ offset: true }),
    duration_seconds: z.number().finite().nonnegative().nullable(),
    source_count: z.number().int().nonnegative(),
    retrieval_count: z.number().int().nonnegative(),
    degraded: z.boolean(),
    warnings: z.array(labWarningSchema).max(10),
  })
  .strict()

export const labRunStageSchema = z
  .object({
    name: z.enum([
      'source',
      'index',
      'retrieve',
      'retrieving',
      'generate',
      'generating',
      'verify',
      'reviewing',
      'finished',
    ]),
    status: z.enum([
      'completed',
      'running',
      'attention',
      'pending',
      'unavailable',
    ]),
    duration_seconds: z.number().finite().nonnegative().nullable(),
    count: z.number().int().nonnegative().nullable(),
    message: z.string().min(1).max(180),
  })
  .strict()

export const labRunDetailSchema = labRunSummarySchema.extend({
  stages: z.array(labRunStageSchema).min(1).max(12),
})

export const labRunListSchema = z
  .object({
    items: z.array(labRunSummarySchema).max(50),
    warnings: z.array(labWarningSchema).max(20),
  })
  .strict()

export const labOverviewSchema = z
  .object({
    generated_at: z.string().datetime({ offset: true }),
    status: z.enum(['healthy', 'attention', 'partial', 'no_data']),
    gated_passed: z.number().int().nonnegative(),
    gated_total: z.number().int().nonnegative(),
    held_out_passed: z.number().int().nonnegative(),
    held_out_total: z.number().int().nonnegative(),
    recent_successful_runs: z.number().int().nonnegative(),
    degraded_or_failed_runs: z.number().int().nonnegative(),
    suites: z.array(labSuiteSchema).max(20),
    features: z.array(featureHealthSchema).max(4),
    warnings: z.array(labWarningSchema).max(20),
    limitations: z.array(z.string().min(1).max(500)).max(20),
  })
  .strict()

export type LabOverview = z.infer<typeof labOverviewSchema>
export type LabMetric = z.infer<typeof labMetricSchema>
export type LabSuite = z.infer<typeof labSuiteSchema>
export type LabRunSummary = z.infer<typeof labRunSummarySchema>
export type LabRunDetail = z.infer<typeof labRunDetailSchema>
export type LabRunState = z.infer<typeof runStateSchema>
export type LabWorkflow = z.infer<typeof workflowSchema>
export type LabEvidenceCategory = z.infer<typeof evidenceCategorySchema>
export type LabFeature = z.infer<typeof featureSchema>
