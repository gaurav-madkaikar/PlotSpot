import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { useAuth } from './auth'
import {
  AccountApiError,
  getPersonal,
  savePersonal,
  importPersonal,
} from './account-api'
import {
  readCollection,
  writeCollection,
  clearGuestCollection,
  cleanName,
  nameKey,
  type CollectionState,
} from './collection-storage'
import type { PersonalSnapshot } from './account-contracts'
export type { NamedCollection } from './collection-storage'
type CollectionResult =
  { id: string; error?: never } | { error: string; id?: never }
type Value = CollectionState & {
  saveMovie: (id: number) => Promise<boolean>
  removeSaved: (id: number) => Promise<boolean>
  setMovieCollections: (id: number, ids: string[]) => Promise<boolean>
  createCollection: (name: string) => Promise<CollectionResult>
  renameCollection: (id: string, name: string) => Promise<string | null>
  deleteCollection: (id: string) => Promise<boolean>
  toggleWatched: (id: number) => Promise<boolean>
  importBrowser: () => Promise<boolean>
  retry: () => void
  loading: boolean
  saving: boolean
  loadError: boolean
  message: string
  storageWarning: string
}
const Context = createContext<Value | null>(null)
const empty: CollectionState = { saved: [], watched: [], collections: [] }

export function CollectionProvider({ children }: { children: ReactNode }) {
  const auth = useAuth()
  const owner = auth.user?.id ?? null
  const [initial] = useState(() =>
    owner ? { state: empty, warning: '' } : readCollection(),
  )
  const [state, setState] = useState<PersonalSnapshot>({
    ...initial.state,
    revision: 0,
  })
  const current = useRef(state)
  const identity = useRef(auth)
  identity.current = auth
  const mounted = useRef(true)
  const locked = useRef(false)
  const sessionRecovery = useRef(false)
  const [message, setMessage] = useState('')
  const [storageWarning, setWarning] = useState(initial.warning)
  const [loading, setLoading] = useState(Boolean(owner))
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState(false)
  const [reload, setReload] = useState(0)
  function update(next: PersonalSnapshot) {
    if (next.revision < current.current.revision) return
    current.current = next
    setState(next)
  }
  const valid = (id: string | null) =>
    mounted.current &&
    (identity.current.user?.id ?? null) === id &&
    identity.current.status === (id ? 'authenticated' : 'guest')
  function recoverSession() {
    if (sessionRecovery.current) return
    sessionRecovery.current = true
    void auth.refresh()
  }
  useEffect(() => {
    sessionRecovery.current = false
  }, [auth.csrf])
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])
  useEffect(() => {
    if (!owner || auth.status !== 'authenticated') return
    const controller = new AbortController()
    setLoading(true)
    setLoadError(false)
    getPersonal(owner, controller.signal)
      .then((next) => {
        if (valid(owner)) {
          update(next)
          setWarning('')
        }
      })
      .catch((issue) => {
        if (controller.signal.aborted || !valid(owner)) return
        setLoadError(true)
        setWarning(
          'Your account collection could not be loaded. Retry before making changes.',
        )
        if (
          issue instanceof AccountApiError &&
          [401, 403].includes(issue.status)
        )
          recoverSession()
      })
      .finally(() => {
        if (!controller.signal.aborted && mounted.current) setLoading(false)
      })
    return () => controller.abort()
  }, [owner, auth.status, reload, auth.refresh])

  async function change(
    transform: (state: PersonalSnapshot) => PersonalSnapshot,
    success: string,
    importing = false,
  ) {
    if (locked.current || loading || loadError || !valid(owner)) return false
    locked.current = true
    setSaving(true)
    try {
      const next = transform(current.current)
      let stored = next
      if (owner) {
        stored = importing
          ? await importPersonal(
              owner,
              readCollectionForImport(),
              current.current.revision,
              identity.current.csrf,
            )
          : await savePersonal(owner, next, identity.current.csrf)
      } else {
        const { revision: _, ...guest } = next
        writeCollection(guest)
        setWarning('')
      }
      if (!valid(owner)) return false
      update(stored)
      if (importing) clearGuestCollection()
      setMessage(success)
      if (owner) setWarning('')
      return true
    } catch (issue) {
      if (!valid(owner)) return false
      const text =
        issue instanceof Error
          ? issue.message
          : 'Your changes could not be saved. Try again.'
      setWarning(text)
      if (owner && issue instanceof AccountApiError) {
        if ([401, 403].includes(issue.status)) recoverSession()
        if (issue.status === 409) {
          try {
            const latest = await getPersonal(owner)
            if (valid(owner)) update(latest)
          } catch {
            if (valid(owner)) {
              setLoadError(true)
              setWarning(
                'Your account collection could not be reloaded. Retry before making changes.',
              )
            }
          }
        }
      }
      return false
    } finally {
      locked.current = false
      if (mounted.current) setSaving(false)
    }
  }
  function readCollectionForImport() {
    const guest = readCollection()
    if (guest.warning)
      throw new Error(
        'Temporary saves could not be read. Nothing was imported.',
      )
    return guest.state
  }
  function nameError(name: string, except?: string) {
    if (!name) return 'Enter a collection name.'
    if (name.length > 60) return 'Use 60 characters or fewer.'
    if (nameKey(name) === 'all saved')
      return 'All saved is reserved for your default collection.'
    if (
      current.current.collections.some(
        (c) => c.id !== except && nameKey(c.name) === nameKey(name),
      )
    )
      return 'A collection with this name already exists.'
    return null
  }
  async function createCollection(input: string): Promise<CollectionResult> {
    const name = cleanName(input)
    const error = nameError(name)
    if (error) return { error }
    const id = crypto.randomUUID()
    const done = await change(
      (s) => ({
        ...s,
        collections: [...s.collections, { id, name, movieIds: [] }],
      }),
      `${name} created.`,
    )
    return done
      ? { id }
      : {
          error:
            'The collection could not be created. Review the message and try again.',
        }
  }
  async function renameCollection(id: string, input: string) {
    const name = cleanName(input)
    const error = nameError(name, id)
    if (error) return error
    const done = await change(
      (s) => ({
        ...s,
        collections: s.collections.map((c) =>
          c.id === id ? { ...c, name } : c,
        ),
      }),
      'Collection renamed.',
    )
    return done ? null : 'The collection could not be renamed. Try again.'
  }
  const available = auth.status === 'guest' || auth.status === 'authenticated'
  const visible = available && !loading && !loadError ? state : empty
  return (
    <Context.Provider
      value={{
        ...visible,
        message,
        storageWarning,
        loading: loading || !available,
        saving,
        loadError,
        retry: () => {
          sessionRecovery.current = false
          setReload((n) => n + 1)
        },
        createCollection,
        renameCollection,
        saveMovie: (id) =>
          change(
            (s) => ({ ...s, saved: [...new Set([...s.saved, id])] }),
            'Movie saved to All saved.',
          ),
        removeSaved: (id) =>
          change(
            (s) => ({
              ...s,
              saved: s.saved.filter((n) => n !== id),
              collections: s.collections.map((c) => ({
                ...c,
                movieIds: c.movieIds.filter((n) => n !== id),
              })),
            }),
            'Movie removed from all collections.',
          ),
        setMovieCollections: (id, ids) =>
          change(
            (s) => ({
              ...s,
              saved: [...new Set([...s.saved, id])],
              collections: s.collections.map((c) => ({
                ...c,
                movieIds: ids.includes(c.id)
                  ? [...new Set([...c.movieIds, id])]
                  : c.movieIds.filter((n) => n !== id),
              })),
            }),
            'Movie collections updated.',
          ),
        deleteCollection: (id) =>
          change(
            (s) => ({
              ...s,
              collections: s.collections.filter((c) => c.id !== id),
            }),
            'Collection deleted. Its movies are still in All saved.',
          ),
        toggleWatched: (id) =>
          change(
            (s) => ({
              ...s,
              watched: s.watched.includes(id)
                ? s.watched.filter((n) => n !== id)
                : [...s.watched, id],
            }),
            'Spoiler preference updated.',
          ),
        importBrowser: () =>
          owner
            ? change((s) => s, 'Temporary saves added to your account.', true)
            : Promise.resolve(false),
      }}
    >
      {children}
    </Context.Provider>
  )
}
export function useCollection() {
  const value = useContext(Context)
  if (!value) throw new Error('CollectionProvider is missing')
  return value
}
