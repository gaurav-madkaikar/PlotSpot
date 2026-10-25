import { z } from 'zod'
import {
  labOverviewSchema,
  labRunDetailSchema,
  labRunListSchema,
  type LabRunState,
  type LabWorkflow,
} from './lab-contracts'

export class LabApiError extends Error {
  constructor(public status: number) {
    super(
      status === 404
        ? 'The developer lab is not enabled.'
        : 'Reliability data could not be loaded.',
    )
  }
}

async function labRequest<T>(
  path: string,
  schema: z.ZodType<T>,
  signal?: AbortSignal,
) {
  const response = await fetch(path, {
    method: 'GET',
    cache: 'no-store',
    credentials: 'same-origin',
    signal,
  })
  if (!response.ok) throw new LabApiError(response.status)
  return schema.parse(await response.json())
}

export function getLabOverview(signal?: AbortSignal) {
  return labRequest('/api/lab/overview', labOverviewSchema, signal)
}

export function getLabRuns(
  filters: {
    workflow?: LabWorkflow
    state?: LabRunState
    limit?: number
  },
  signal?: AbortSignal,
) {
  const parameters = new URLSearchParams()
  if (filters.workflow) parameters.set('workflow', filters.workflow)
  if (filters.state) parameters.set('state', filters.state)
  parameters.set('limit', String(filters.limit ?? 20))
  return labRequest(`/api/lab/runs?${parameters}`, labRunListSchema, signal)
}

export function getLabRun(id: string, signal?: AbortSignal) {
  if (!/^(?:prep|story)_[a-f0-9]{32}$/.test(id))
    throw new Error('Invalid reliability run ID')
  return labRequest(`/api/lab/runs/${id}`, labRunDetailSchema, signal)
}
