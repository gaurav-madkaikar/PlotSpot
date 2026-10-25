import type { z } from 'zod'
import type { personNameSchema } from './contracts'

type Kind = 'movie' | 'actor' | 'director'
type LocalSuggestion = { label: string; kind: Kind }
type Person = z.infer<typeof personNameSchema>

export type SearchOption = LocalSuggestion & {
  key: string
  personId?: number
  context?: string
}

function normalize(value: string) {
  return value
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim()
}

/** One suggestion list, without turning arbitrary title matches into person choices. */
export function searchSuggestionOptions(
  query: string,
  local: LocalSuggestion[],
  people: Person[],
  resultTitles: string[] = [],
): SearchOption[] {
  const needle = normalize(query)
  // Also guard against stale suggestion responses from an earlier catalog version.
  if (!needle || resultTitles.some((title) => normalize(title) === needle))
    return []
  const knownNames = new Set(
    local
      .filter((item) => item.kind !== 'movie')
      .map((item) => normalize(item.label)),
  )
  const words = needle.split(' ')
  const persons: SearchOption[] = people.flatMap((person) => {
    const name = normalize(person.name)
    const nameWords = name.split(' ')
    const kind =
      person.known_for_department === 'Directing'
        ? 'director'
        : person.known_for_department === 'Acting'
          ? 'actor'
          : null
    // Multiword name prefixes, known corrections, and exact surnames are useful.
    // A one-word title such as Batman must not offer arbitrary people containing it.
    const relevant =
      knownNames.has(name) ||
      (words.length > 1 && name.startsWith(needle)) ||
      (words.length === 1 &&
        nameWords.length > 1 &&
        nameWords.at(-1) === needle)
    if (!kind || !relevant) return []
    return [
      {
        key: `person:${person.id}:${kind}`,
        label: person.name,
        kind,
        personId: person.id,
        context: person.known_for_titles[0],
      },
    ]
  })
  // Specific identities replace generic same-name corrections; remakes and different roles remain distinct.
  const specificNames = new Set(
    persons.map((item) => `${item.kind}:${normalize(item.label)}`),
  )
  const generic = local
    .filter(
      (item) => !specificNames.has(`${item.kind}:${normalize(item.label)}`),
    )
    .map((item) => ({ ...item, key: `${item.kind}:${normalize(item.label)}` }))
  return Array.from(
    new Map([...generic, ...persons].map((item) => [item.key, item])).values(),
  )
}
