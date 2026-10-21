import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import {
  getSession,
  authenticate,
  signOut,
  AccountApiError,
  registerAccount,
  resendVerification,
  verifyEmail,
  savePreferences,
} from './account-api'
import type {
  AccountSession,
  VerificationReceipt,
  AccountPreferences,
} from './account-contracts'

type AuthStatus = 'checking' | 'guest' | 'authenticated' | 'error'
type AuthValue = {
  user: AccountSession['user']
  csrf: string
  status: AuthStatus
  busy: boolean
  error: string
  refresh: () => Promise<boolean>
  login: (username: string, password: string) => Promise<boolean>
  register: (
    username: string,
    password: string,
    email: string,
  ) => Promise<VerificationReceipt | null>
  resend: (
    username: string,
    password: string,
  ) => Promise<VerificationReceipt | null>
  verify: (token: string) => Promise<boolean>
  updatePreferences: (preferences: AccountPreferences) => Promise<boolean>
  logout: () => Promise<boolean>
}
const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AccountSession | null>(null)
  const [status, setStatus] = useState<AuthStatus>('checking')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const current = useRef<AccountSession | null>(null)
  const epoch = useRef(0)
  const mutation = useRef(false)
  const request = useRef<AbortController | null>(null)
  const channel = useRef<BroadcastChannel | null>(null)
  const apply = useCallback((next: AccountSession) => {
    current.current = next
    setSession(next)
    setStatus(next.user ? 'authenticated' : 'guest')
    setError('')
  }, [])
  const refresh = useCallback(async () => {
    if (
      mutation.current ||
      (request.current && !request.current.signal.aborted)
    )
      return false
    const generation = ++epoch.current
    request.current?.abort()
    const controller = new AbortController()
    request.current = controller
    setStatus('checking')
    try {
      const next = await getSession(controller.signal)
      if (epoch.current === generation) apply(next)
      return true
    } catch (issue) {
      if (!controller.signal.aborted && epoch.current === generation) {
        setStatus('error')
        setError('Account access is unavailable. Retry to continue.')
      }
      return false
    } finally {
      if (request.current === controller) request.current = null
    }
  }, [apply])
  useEffect(() => {
    // StrictMode replays effects. Defer bootstrap until its disposable first
    // setup has cleaned up, avoiding competing anonymous Set-Cookie responses.
    let disposed = false
    queueMicrotask(() => {
      if (!disposed) void refresh()
    })
    const check = () => void refresh()
    window.addEventListener('focus', check)
    if (typeof BroadcastChannel !== 'undefined') {
      channel.current = new BroadcastChannel('frame.account')
      channel.current.onmessage = check
    }
    return () => {
      disposed = true
      request.current?.abort()
      ++epoch.current
      window.removeEventListener('focus', check)
      channel.current?.close()
    }
  }, [refresh])
  async function change(
    run: (csrf: string) => Promise<AccountSession>,
    conflicts = false,
  ) {
    if (
      mutation.current ||
      !current.current ||
      status === 'checking' ||
      status === 'error'
    )
      return false
    mutation.current = true
    setBusy(true)
    setError('')
    ++epoch.current
    request.current?.abort()
    let recover = false
    let feedback = ''
    try {
      apply(await run(current.current.csrf_token))
      channel.current?.postMessage({ type: 'session-changed' })
      return true
    } catch (issue) {
      feedback =
        issue instanceof Error
          ? issue.message
          : 'Account access is unavailable. Try again.'
      setError(feedback)
      recover =
        issue instanceof AccountApiError &&
        [401, 403, ...(conflicts ? [409] : [])].includes(issue.status)
      return false
    } finally {
      mutation.current = false
      if (recover) {
        await refresh()
        setError(feedback)
      }
      setBusy(false)
    }
  }
  // Verification receipts never become authenticated sessions. Reuse the same
  // mutation lock and recovery boundary without broadcasting a false sign-in.
  async function verification<T>(
    run: (csrf: string) => Promise<T>,
  ): Promise<T | null> {
    if (
      mutation.current ||
      !current.current ||
      status === 'checking' ||
      status === 'error'
    )
      return null
    mutation.current = true
    setBusy(true)
    setError('')
    ++epoch.current
    request.current?.abort()
    let recover = false
    let feedback = ''
    try {
      return await run(current.current.csrf_token)
    } catch (issue) {
      feedback =
        issue instanceof Error
          ? issue.message
          : 'Verification is unavailable. Try again.'
      setError(feedback)
      recover =
        issue instanceof AccountApiError && [401, 403].includes(issue.status)
      return null
    } finally {
      mutation.current = false
      if (recover) {
        await refresh()
        setError(feedback)
      }
      setBusy(false)
    }
  }
  return (
    <AuthContext.Provider
      value={{
        user: session?.user ?? null,
        csrf: session?.csrf_token ?? '',
        status,
        busy,
        error,
        refresh,
        login: (username, password) =>
          change((csrf) => authenticate(username, password, csrf)),
        register: (username, password, email) =>
          verification((csrf) =>
            registerAccount(username, password, email, csrf),
          ),
        resend: (username, password) =>
          verification((csrf) => resendVerification(username, password, csrf)),
        verify: async (token) =>
          Boolean(await verification((csrf) => verifyEmail(token, csrf))),
        updatePreferences: (preferences) => {
          const owner = current.current?.user?.id
          return owner
            ? change((csrf) => savePreferences(owner, preferences, csrf), true)
            : Promise.resolve(false)
        },
        logout: () => change(signOut),
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('AuthProvider is missing')
  return value
}
