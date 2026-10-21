import { z } from 'zod'
import { AccountApiError } from './account-api'
import {
  postPageSchema,
  threadViewSchema,
  capabilitiesSchema,
  mutationSchema,
  reportPageSchema,
  type PostKind,
  type PostDraft,
} from './community-contracts'
async function request<T extends { viewer_id: string }>(
  owner: string,
  path: string,
  schema: z.ZodType<T>,
  options: RequestInit = {},
) {
  const response = await fetch(path, {
    credentials: 'same-origin',
    cache: 'no-store',
    ...options,
  })
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new AccountApiError(
      response.status,
      typeof data?.detail === 'string' && data.detail.length <= 250
        ? data.detail
        : 'The discussion could not be loaded. Please retry.',
    )
  }
  let parsed: T
  try {
    parsed = schema.parse(await response.json())
  } catch {
    throw new AccountApiError(
      502,
      'The discussion response could not be verified.',
    )
  }
  if (parsed.viewer_id !== owner)
    throw new AccountApiError(401, 'Your account changed. Sign in again.')
  return parsed
}
const json = (body: object, csrf: string, method = 'POST'): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
  body: JSON.stringify(body),
})
const query = (page: number, allowed: boolean) =>
  new URLSearchParams({ page: String(page), allow_spoilers: String(allowed) })
export const communityCapabilities = (owner: string, signal: AbortSignal) =>
  request(owner, '/api/community/capabilities', capabilitiesSchema, { signal })
export const loadThreads = (
  owner: string,
  movie: number,
  page: number,
  allowed: boolean,
  signal: AbortSignal,
) =>
  request(
    owner,
    `/api/movies/${movie}/threads?${query(page, allowed)}`,
    postPageSchema,
    { signal },
  )
export const loadThread = (
  owner: string,
  id: number,
  allowed: boolean,
  signal: AbortSignal,
) =>
  request(
    owner,
    `/api/community/threads/${id}?allow_spoilers=${allowed}`,
    threadViewSchema,
    { signal },
  )
export const loadReplies = (
  owner: string,
  id: number,
  page: number,
  allowed: boolean,
  signal: AbortSignal,
) =>
  request(
    owner,
    `/api/community/threads/${id}/replies?${query(page, allowed)}`,
    postPageSchema,
    { signal },
  )
export const createThread = (
  owner: string,
  movie: number,
  draft: PostDraft,
  key: string,
  csrf: string,
) =>
  request(
    owner,
    `/api/movies/${movie}/threads`,
    mutationSchema,
    json({ ...draft, request_key: key }, csrf),
  )
export const createReply = (
  owner: string,
  id: number,
  draft: PostDraft,
  parent: number | null,
  key: string,
  csrf: string,
) =>
  request(
    owner,
    `/api/community/threads/${id}/replies`,
    mutationSchema,
    json(
      {
        body: draft.body,
        spoilers: draft.spoilers,
        parent_id: parent,
        request_key: key,
      },
      csrf,
    ),
  )
const plural = (kind: PostKind) => (kind === 'thread' ? 'threads' : 'replies')
export const editPost = (
  owner: string,
  kind: PostKind,
  id: number,
  draft: PostDraft,
  revision: number,
  csrf: string,
) =>
  request(
    owner,
    `/api/community/${plural(kind)}/${id}`,
    mutationSchema,
    json({ ...draft, revision }, csrf, 'PATCH'),
  )
export const deletePost = (
  owner: string,
  kind: PostKind,
  id: number,
  revision: number,
  csrf: string,
) =>
  request(
    owner,
    `/api/community/${plural(kind)}/${id}/delete`,
    mutationSchema,
    json({ revision }, csrf),
  )
export const reportPost = (
  owner: string,
  kind: PostKind,
  id: number,
  reason: string,
  details: string,
  csrf: string,
) =>
  request(
    owner,
    '/api/community/reports',
    mutationSchema,
    json({ kind, target_id: id, reason, details }, csrf),
  )
export const loadReports = (
  owner: string,
  page: number,
  allowed: boolean,
  state: 'open' | 'resolved',
  signal: AbortSignal,
) =>
  request(
    owner,
    `/api/community/reports?${query(page, allowed)}&state=${state}`,
    reportPageSchema,
    { signal },
  )
export const reviewReport = (
  owner: string,
  id: number,
  revision: number,
  action: 'dismiss' | 'hide' | 'restore',
  csrf: string,
) =>
  request(
    owner,
    `/api/community/reports/${id}/review`,
    mutationSchema,
    json({ action, revision }, csrf),
  )
