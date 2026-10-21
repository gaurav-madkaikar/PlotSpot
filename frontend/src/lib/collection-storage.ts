import { z } from 'zod'

export const storageKey = 'frame.demo.collection.v1'
const movieIds = z.array(z.number().int().positive())
const collectionSchema = z.object({
  saved: movieIds,
  watched: movieIds,
  // Older browser saves have no custom collections.
  collections: z
    .array(
      z.object({
        id: z.string().min(1).max(100),
        name: z.string().trim().min(1).max(60),
        movieIds,
      }),
    )
    .default([]),
})
export type CollectionState = z.infer<typeof collectionSchema>
export type NamedCollection = CollectionState['collections'][number]
export const cleanName = (name: string) =>
  name.normalize('NFKC').trim().replace(/\s+/g, ' ')
export const nameKey = (name: string) => cleanName(name).toLowerCase()

// Per-document memory survives SPA navigation and provider remounts, never reloads.
// sessionStorage would survive reload too, so it deliberately isn't used here.
let guestState: CollectionState = { saved: [], watched: [], collections: [] }

// Retire only the app's historical guest cache. Account saves live on the server.
try {
  localStorage.removeItem(storageKey)
} catch {
  /* Storage may be blocked. */
}

export function readCollection(): { state: CollectionState; warning: string } {
  return { state: structuredClone(guestState), warning: '' }
}
export function writeCollection(state: CollectionState) {
  guestState = structuredClone(collectionSchema.parse(state))
}
export function clearGuestCollection() {
  guestState = { saved: [], watched: [], collections: [] }
}
