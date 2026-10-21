import { z } from 'zod'
import {
  sessionSchema,
  personalViewSchema,
  verificationSchema,
  verifiedSchema,
  type PersonalSnapshot,
  type AccountPreferences,
} from './account-contracts'
import type { CollectionState } from './collection-storage'

export class AccountApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}
async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(path, {
    credentials: 'same-origin',
    cache: 'no-store',
    ...options,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new AccountApiError(
      response.status,
      typeof body?.detail === 'string' && body.detail.length <= 250
        ? body.detail
        : 'Account access is unavailable. Try again shortly.',
    )
  }
  try {
    return schema.parse(await response.json())
  } catch {
    throw new AccountApiError(
      502,
      'The account response could not be verified. Retry shortly.',
    )
  }
}
const json = (body: object, csrf: string, method = 'POST'): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
  body: JSON.stringify(body),
})
export const getSession = (signal?: AbortSignal) =>
  request('/api/auth/session', sessionSchema, { signal })
export const authenticate = (
  username: string,
  password: string,
  csrf: string,
) =>
  request('/api/auth/login', sessionSchema, json({ username, password }, csrf))
export const registerAccount = (
  username: string,
  password: string,
  email: string,
  csrf: string,
) =>
  request(
    '/api/auth/register',
    verificationSchema,
    json({ username, password, email }, csrf),
  )
export const resendVerification = (
  username: string,
  password: string,
  csrf: string,
) =>
  request(
    '/api/auth/resend-verification',
    verificationSchema,
    json({ username, password }, csrf),
  )
export const verifyEmail = (token: string, csrf: string) =>
  request('/api/auth/verify-email', verifiedSchema, json({ token }, csrf))
export const signOut = (csrf: string) =>
  request('/api/auth/logout', sessionSchema, json({}, csrf))
async function personal(
  owner: string,
  options: RequestInit = {},
  path = '/api/me/collection',
) {
  const result = await request(path, personalViewSchema, options)
  // Cookie identity can change in another tab between auth bootstrap and this read.
  if (result.owner_id !== owner)
    throw new AccountApiError(
      401,
      'Your account changed. Refresh the page to continue.',
    )
  return result.snapshot
}
export const getPersonal = (owner: string, signal?: AbortSignal) =>
  personal(owner, { signal })
export const savePersonal = (
  owner: string,
  state: PersonalSnapshot,
  csrf: string,
) => personal(owner, json(state, csrf, 'PUT'))
export const importPersonal = (
  owner: string,
  state: CollectionState,
  revision: number,
  csrf: string,
) =>
  personal(
    owner,
    json({ ...state, revision }, csrf),
    '/api/me/collection/import',
  )

export const savePreferences = (
  owner: string,
  preferences: AccountPreferences,
  csrf: string,
) =>
  request(
    '/api/me/preferences',
    sessionSchema,
    json(preferences, csrf, 'PUT'),
  ).then((session) => {
    if (session.user?.id !== owner)
      throw new AccountApiError(
        401,
        'Your account changed. Refresh the page to continue.',
      )
    return session
  })

export { request as accountRequest, json as accountJson }
