import { z } from 'zod'
export const preferencesSchema = z
  .object({
    revision: z.number().int().nonnegative().max(Number.MAX_SAFE_INTEGER),
    allow_spoilers: z.boolean(),
    include_adult: z.boolean(),
    track_movie_history: z.boolean().default(true),
  })
  .strict()
export type AccountPreferences = z.infer<typeof preferencesSchema>
export const sessionSchema = z.object({
  user: z
    .object({
      preferences: preferencesSchema.default({
        revision: 0,
        allow_spoilers: false,
        include_adult: true,
        track_movie_history: true,
      }),
      id: z.string().regex(/^[a-f0-9]{32}$/),
      username: z.string().min(3).max(32),
    })
    .nullable(),
  csrf_token: z.string().regex(/^[A-Za-z0-9_-]{43}$/),
})
export type AccountSession = z.infer<typeof sessionSchema>
export const verificationSchema = z.object({
  status: z.literal('verification_required'),
  preview_url: z
    .string()
    .regex(/^\/account#verify=[A-Za-z0-9_-]{43}$/)
    .nullable(),
})
export type VerificationReceipt = z.infer<typeof verificationSchema>
export const verifiedSchema = z.object({ status: z.literal('verified') })
const ids = z.array(z.number().int().positive().max(2147483647)).max(2000)
export const personalSchema = z.object({
  revision: z.number().int().nonnegative().max(Number.MAX_SAFE_INTEGER),
  saved: ids,
  watched: ids,
  collections: z
    .array(
      z.object({
        id: z.string().uuid(),
        name: z.string().min(1).max(60),
        movieIds: ids,
      }),
    )
    .max(50),
})
export type PersonalSnapshot = z.infer<typeof personalSchema>
export const personalViewSchema = z.object({
  owner_id: z.string().regex(/^[a-f0-9]{32}$/),
  snapshot: personalSchema,
})
