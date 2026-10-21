import { z } from 'zod'
import {
  draftStatusSchema,
  watchRegionsSchema,
  watchOptionsSchema,
  relatedMoviesSchema,
  nameSearchSchema,
  movieSchema,
  movieFeaturesSchema,
  movieSearchSchema,
  healthSchema,
  suggestionSchema,
  movieAnswerSchema,
  movieQuizSchema,
  movieFactsSchema,
} from './contracts'

export class ApiError extends Error {
  constructor(public status: number) {
    super(
      status === 404
        ? 'This movie is not in the collection.'
        : 'The collection could not be loaded.',
    )
  }
}

async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(path, {
    signal,
    ...(/\/(features|facts|quiz)(?:\?|$)/.test(path)
      ? { cache: 'no-store' as const, credentials: 'same-origin' as const }
      : {}),
  })
  if (!response.ok) throw new ApiError(response.status)
  // TypeScript checks our code; Zod checks data arriving from another process.
  return schema.parse(await response.json())
}

export function searchMovies(params: URLSearchParams, signal?: AbortSignal) {
  const unified = params.get('unified') === 'true'
  const clean = new URLSearchParams(params)
  clean.delete('unified')
  return request(
    `${unified ? '/api/search/catalog' : '/api/search'}?${clean.toString()}`,
    movieSearchSchema,
    signal,
  )
}

export function searchSavedMovies(
  params: URLSearchParams,
  signal?: AbortSignal,
) {
  const clean = new URLSearchParams(params)
  for (const field of ['unified', 'page', 'search_token', 'person_id', 'role'])
    clean.delete(field)
  return request(`/api/search/local?${clean}`, movieSearchSchema, signal)
}

export function getMovie(id: number, signal?: AbortSignal) {
  return request(`/api/movies/${id}`, movieSchema, signal)
}

export function getHealth(signal?: AbortSignal) {
  return request('/api/health', healthSchema, signal)
}

export function getSuggestions(
  query: string,
  signal?: AbortSignal,
  includeAdult = true,
) {
  return request(
    `/api/search/suggestions?${new URLSearchParams({ q: query, ...(includeAdult ? {} : { include_adult: 'false' }) })}`,
    suggestionSchema,
    signal,
  )
}

async function movieAction(
  path: string,
  body: object,
  signal: AbortSignal,
  csrf: string,
) {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
    credentials: 'same-origin',
    cache: 'no-store',
    signal,
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    const messages: Record<number, string> = {
      409: 'Another question is being answered. Try again shortly.',
      502: 'No new content passed verification. Your saved content is unchanged; try again.',
      503: 'A movie source or AI service is unavailable. Try again shortly.',
      504: 'This question took too long. Try again.',
    }
    const detail = await response.json().catch(() => null)
    throw new Error(
      path.endsWith('/quiz/more') &&
        typeof detail?.detail === 'string' &&
        detail.detail.length <= 250
        ? detail.detail
        : (messages[response.status] ??
            'Your question could not be answered. Please try again.'),
    )
  }
  return response.json()
}

export async function askMovie(
  id: number,
  question: string,
  allowSpoilers: boolean,
  signal: AbortSignal,
  csrf: string,
) {
  return movieAnswerSchema.parse(
    await movieAction(
      `/api/movies/${id}/questions`,
      { question, allow_spoilers: allowSpoilers },
      signal,
      csrf,
    ),
  )
}

export async function buildMovieQuiz(
  id: number,
  allowSpoilers: boolean,
  signal: AbortSignal,
) {
  return request(
    `/api/movies/${id}/quiz?allow_spoilers=${allowSpoilers}`,
    movieQuizSchema,
    signal,
  )
}

export async function loadMovieFacts(
  id: number,
  allowSpoilers: boolean,
  signal: AbortSignal,
) {
  return request(
    `/api/movies/${id}/facts?allow_spoilers=${allowSpoilers}`,
    movieFactsSchema,
    signal,
  )
}

export async function generateMoreQuiz(
  id: number,
  signal: AbortSignal,
  csrf: string,
) {
  return movieQuizSchema.parse(
    await movieAction(
      `/api/movies/${id}/quiz/more`,
      { allow_spoilers: true },
      signal,
      csrf,
    ),
  )
}

export async function getMovieFeatures(id: number, signal?: AbortSignal) {
  const features = await request(
    `/api/movies/${id}/features`,
    movieFeaturesSchema,
    signal,
  )
  if (features.movie_id !== id)
    throw new Error('Feature availability returned the wrong movie.')
  return features
}

export async function searchNames(
  params: URLSearchParams,
  signal?: AbortSignal,
) {
  const response = await fetch(`/api/search/names?${params}`, { signal })
  if (!response.ok)
    throw new Error('Name search is unavailable. Please try again.')
  return nameSearchSchema.parse(await response.json())
}

export function getWatchRegions(signal?: AbortSignal) {
  return request('/api/watch-regions', watchRegionsSchema, signal)
}
export function getWatchOptions(
  id: number,
  country: string,
  signal?: AbortSignal,
) {
  return request(
    `/api/movies/${id}/watch?country=${encodeURIComponent(country)}`,
    watchOptionsSchema,
    signal,
  )
}
export function getRelatedMovies(id: number, signal?: AbortSignal) {
  return request(`/api/movies/${id}/related`, relatedMoviesSchema, signal)
}

async function draftRequest(
  id: number,
  jobId?: string | null,
  signal?: AbortSignal,
) {
  const path = `/api/movies/${id}/preparation${jobId ? '/cancel' : jobId === null ? '' : '?allow_spoilers=true'}`
  const response = await fetch(
    path,
    jobId !== undefined
      ? {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal,
          body: JSON.stringify({
            allow_spoilers: true,
            ...(jobId ? { job_id: jobId } : {}),
          }),
        }
      : { signal },
  )
  if (!response.ok) {
    const detail = await response.json().catch(() => null)
    throw new Error(
      typeof detail?.detail === 'string' && detail.detail.length <= 250
        ? detail.detail
        : 'Draft preparation is unavailable. Please try again.',
    )
  }
  const parsed = draftStatusSchema.safeParse(await response.json())
  if (!parsed.success)
    throw new Error('The draft response could not be verified.')
  const result = parsed.data
  if (
    result.job &&
    (result.job.movie_id !== id ||
      result.job.items.some((item) => item.origin.movie_id !== id))
  ) {
    throw new Error('The draft response belongs to another movie.')
  }
  return result
}
export function getPreparation(id: number, signal?: AbortSignal) {
  return draftRequest(id, undefined, signal)
}
export function startPreparation(id: number) {
  return draftRequest(id, null)
}
export function cancelPreparation(id: number, jobId: string) {
  return draftRequest(id, jobId)
}
