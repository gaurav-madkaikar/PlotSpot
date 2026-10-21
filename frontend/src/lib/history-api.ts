import { z } from 'zod'
import { accountRequest, accountJson, AccountApiError } from './account-api'

export type HistoryKind = 'movies' | 'quizzes'
const entrySchema = z
  .object({
    id: z.string().uuid(),
    movie_id: z.number().int().positive(),
    title: z.string(),
    cover_url: z.string().nullable(),
    occurred_at: z.string().datetime({ offset: true }),
    score: z.number().int().nonnegative().nullable(),
    scored_questions: z.number().int().nonnegative().nullable(),
    total_questions: z.number().int().positive().nullable(),
    content_version: z.string().nullable(),
  })
  .strict()
const pageSchema = z
  .object({
    owner_id: z.string(),
    items: z.array(entrySchema),
    total: z.number().int().nonnegative(),
    page: z.number().int().positive(),
    page_size: z.number().int().positive(),
    total_pages: z.number().int().nonnegative(),
  })
  .strict()
const receiptSchema = z
  .object({
    owner_id: z.string(),
    status: z.enum(['recorded', 'disabled']),
    item: entrySchema.nullable(),
  })
  .strict()
const clearedSchema = z
  .object({ owner_id: z.string(), status: z.literal('cleared') })
  .strict()
export type HistoryEntry = z.infer<typeof entrySchema>
export type HistoryPage = z.infer<typeof pageSchema>
function owned<T extends { owner_id: string }>(owner: string, response: T): T {
  if (response.owner_id !== owner)
    throw new AccountApiError(
      401,
      'Your account changed. Refresh the page to continue.',
    )
  return response
}
function write(
  owner: string,
  csrf: string,
  body: object,
  method = 'POST',
): RequestInit {
  return {
    ...accountJson(body, csrf, method),
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrf,
      'X-Account-Owner': owner,
    },
  }
}
export const getHistory = (
  owner: string,
  kind: HistoryKind,
  page: number,
  signal?: AbortSignal,
) =>
  accountRequest(`/api/me/history/${kind}?page=${page}`, pageSchema, {
    signal,
  }).then((response) => owned(owner, response))
export const clearHistory = (owner: string, kind: HistoryKind, csrf: string) =>
  accountRequest(
    `/api/me/history/${kind}`,
    clearedSchema,
    write(owner, csrf, {}, 'DELETE'),
  ).then((response) => owned(owner, response))
export const recordVisit = (
  owner: string,
  movieId: number,
  eventId: string,
  csrf: string,
  signal?: AbortSignal,
) =>
  accountRequest('/api/me/history/movies', receiptSchema, {
    ...write(owner, csrf, { movie_id: movieId, event_id: eventId }),
    signal,
  }).then((response) => owned(owner, response))
export const recordQuiz = (
  owner: string,
  movieId: number,
  eventId: string,
  version: string,
  preparedAt: string,
  answers: Record<string, number>,
  csrf: string,
  signal?: AbortSignal,
) =>
  accountRequest('/api/me/history/quizzes', receiptSchema, {
    ...write(owner, csrf, {
      movie_id: movieId,
      event_id: eventId,
      content_version: version,
      content_prepared_at: preparedAt,
      allow_spoilers: true,
      answers,
    }),
    signal,
  }).then((response) => owned(owner, response))
