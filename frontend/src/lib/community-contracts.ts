import { z } from 'zod'
const id = z.number().int().positive()
const viewer = z.string().regex(/^[a-f0-9]{32}$/)
export const postSchema = z.object({
  id,
  title: z.string().nullable(),
  body: z.string().nullable(),
  author: z.string(),
  created_at: z.string().datetime({ offset: true }),
  updated_at: z.string().datetime({ offset: true }),
  revision: id,
  spoilers: z.boolean(),
  spoiler_locked: z.boolean(),
  removed: z.boolean(),
  can_edit: z.boolean(),
  can_delete: z.boolean(),
  parent_id: id.nullable(),
  depth: z.number().int().min(0).max(3),
  replies: z.number().int().nonnegative(),
})
export type CommunityPost = z.infer<typeof postSchema>
const pagination = {
  page: id,
  total: z.number().int().nonnegative(),
  has_more: z.boolean(),
}
export const postPageSchema = z.object({
  viewer_id: viewer,
  items: z.array(postSchema),
  ...pagination,
})
export type CommunityPage = z.infer<typeof postPageSchema>
export const threadViewSchema = z.object({
  viewer_id: viewer,
  thread: postSchema,
})
export const capabilitiesSchema = z.object({
  viewer_id: viewer,
  moderator: z.boolean(),
})
export const mutationSchema = z.object({ viewer_id: viewer, id })
export const reportSchema = z.object({
  id,
  kind: z.enum(['thread', 'reply']),
  target_id: id,
  movie_id: id,
  reason: z.string(),
  details: z.string().nullable(),
  reporter: z.string(),
  created_at: z.string(),
  state: z.string(),
  content_state: z.string(),
  title: z.string().nullable(),
  body: z.string().nullable(),
  spoilers: z.boolean(),
  spoiler_locked: z.boolean(),
  revision: id,
})
export type CommunityReport = z.infer<typeof reportSchema>
export const reportPageSchema = z.object({
  viewer_id: viewer,
  items: z.array(reportSchema),
  ...pagination,
})
export type ReportPage = z.infer<typeof reportPageSchema>
export type PostKind = 'thread' | 'reply'
export type PostDraft = { title?: string; body: string; spoilers: boolean }
