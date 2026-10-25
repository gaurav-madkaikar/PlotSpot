import { AccountHistoryPanel } from '../components/account-history-panel'
import { AccountPreferencesPanel } from '../components/account-preferences-panel'
import { safeAccountReturn } from '../lib/account-return'
import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router'
import {
  Eye,
  EyeOff,
  Bookmark,
  FolderHeart,
  LogOut,
  Mail,
  CheckCircle2,
} from 'lucide-react'
import { useAuth } from '../lib/auth'
import { useCollection } from '../lib/collection'
import type { VerificationReceipt } from '../lib/account-contracts'
import { Button } from '../components/ui/button'

export function AccountPage() {
  const auth = useAuth()
  const personal = useCollection()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [receipt, setReceipt] = useState<VerificationReceipt | null>(null)
  const [verificationToken, setVerificationToken] = useState('')
  const [verified, setVerified] = useState(false)
  useEffect(() => {
    if (!location.hash.startsWith('#verify=')) return
    const token = location.hash.slice(8)
    if (/^[A-Za-z0-9_-]{43}$/.test(token)) {
      setVerificationToken(token)
      setReceipt(null)
      setVerified(false)
    } else
      setIssue(
        'This verification link is invalid. Request a new link from Sign in.',
      )
    // Keep credentials out of the address bar and browser history immediately.
    navigate(location.pathname + location.search, { replace: true })
  }, [location.hash, location.pathname, location.search, navigate])
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [visible, setVisible] = useState(false)
  const [issue, setIssue] = useState('')
  const waiting = auth.status === 'checking' && !auth.user
  const accountUnavailable = auth.status === 'error'
  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setIssue('')
    if (!/^[A-Za-z0-9][A-Za-z0-9_.-]{2,31}$/.test(username.trim())) {
      setIssue(
        'Use 3–32 letters, numbers, dots, hyphens or underscores for your username.',
      )
      return
    }
    if (password.length < 6 || password.length > 128) {
      setIssue('Use a password between 6 and 128 characters.')
      return
    }
    if (mode === 'register') {
      const field = document.getElementById(
        'account-email',
      ) as HTMLInputElement | null
      if (!email.trim() || !field?.validity.valid) {
        setIssue('Enter a valid email address.')
        return
      }
      const result = await auth.register(
        username.trim(),
        password,
        email.trim(),
      )
      if (result) {
        setReceipt(result)
        setPassword('')
      }
      return
    }
    if (await auth.login(username.trim(), password)) {
      setPassword('')
      const target = safeAccountReturn(params.get('returnTo'))
      if (target) navigate(target, { replace: true })
    }
  }
  const error = issue || auth.error
  return (
    <div
      className={`page-width account-page ${auth.user ? 'account-page--signed' : 'account-page--access'}`}
    >
      <div className="account-heading">
        <p className="eyebrow">PLOTSPOT ACCOUNT</p>
        <h1>{auth.user ? 'Your account' : 'Your films, in one place'}</h1>
        <p className="page-intro">
          {auth.user
            ? `Signed in as ${auth.user.username}.`
            : 'Save films and organise your collections'}
        </p>
      </div>
      {accountUnavailable ? (
        <div className="status-panel" role="alert">
          <p>{auth.error}</p>
          <Button onClick={() => void auth.refresh()}>Retry account</Button>
        </div>
      ) : waiting ? (
        <div className="status-panel" role="status">
          Opening your account…
        </div>
      ) : verificationToken ? (
        <section
          className="account-card account-verification"
          aria-labelledby="verify-title"
        >
          <Mail size={28} aria-hidden="true" />
          <h2 id="verify-title">Confirm your email.</h2>
          <p>
            Verify the address for the account you created. Then sign in to keep
            your films.
          </p>
          <Button
            disabled={auth.busy}
            onClick={async () => {
              if (await auth.verify(verificationToken)) {
                setVerificationToken('')
                setVerified(true)
                setMode('login')
                setPassword('')
              }
            }}
          >
            {auth.busy ? 'Verifying…' : 'Verify email'}
          </Button>
          {auth.error && (
            <p className="collection-form-error" role="alert">
              {auth.error}
            </p>
          )}
          <Button
            variant="ghost"
            disabled={auth.busy}
            onClick={() => {
              setVerificationToken('')
              setMode('login')
            }}
          >
            Back to sign in
          </Button>
        </section>
      ) : auth.user ? (
        <div className="account-layout">
          <section className="account-card" aria-labelledby="account-library">
            <h2 id="account-library">Your collection, saved.</h2>
            {verified && (
              <p className="account-success" role="status">
                Email verified. Your current session is unchanged. Sign out to
                sign in to the newly verified account.
              </p>
            )}
            <div className="account-totals">
              <div>
                <Bookmark size={20} aria-hidden="true" />
                <strong>
                  {personal.loading ? '…' : personal.saved.length}
                </strong>
                <span>Saved films</span>
              </div>
              <div>
                <FolderHeart size={20} aria-hidden="true" />
                <strong>
                  {personal.loading ? '…' : personal.collections.length}
                </strong>
                <span>Collections</span>
              </div>
            </div>
            {personal.loadError ? (
              <div role="alert">
                <p>Your collection could not be loaded.</p>
                <Button onClick={personal.retry}>Retry collection</Button>
              </div>
            ) : (
              <Button asChild>
                <Link to="/collections">Open collections</Link>
              </Button>
            )}
            <div className="account-signout">
              <Button
                variant="outline"
                disabled={auth.busy || personal.saving}
                onClick={() => void auth.logout()}
              >
                <LogOut size={16} aria-hidden="true" />
                Sign out
              </Button>
            </div>
            {auth.error && (
              <p className="collection-form-error" role="alert">
                {auth.error}
              </p>
            )}
          </section>
          <AccountPreferencesPanel key={auth.user.id} />
          <AccountHistoryPanel key={`history-${auth.user.id}`} />
        </div>
      ) : receipt ? (
        <section
          className="account-card account-verification"
          aria-labelledby="email-sent-title"
        >
          <Mail size={28} aria-hidden="true" />
          <h2 id="email-sent-title">
            {receipt.preview_url
              ? 'Your verification preview.'
              : 'Check your email.'}
          </h2>
          <p>
            {receipt.preview_url
              ? 'Local development mode. No email has been sent.'
              : 'Open the verification link in your inbox before signing in.'}{' '}
            The link expires in 30 minutes.
          </p>
          {receipt.preview_url && (
            <div className="verification-preview">
              <p className="eyebrow">LOCAL EMAIL PREVIEW</p>
              <p>
                Welcome to PlotSpot. Confirm your email to finish creating your
                account.
              </p>
              <Button asChild>
                <Link
                  to={
                    '/account' +
                    (safeAccountReturn(params.get('returnTo'))
                      ? '?returnTo=' +
                        encodeURIComponent(
                          safeAccountReturn(params.get('returnTo'))!,
                        )
                      : '') +
                    receipt.preview_url.slice(receipt.preview_url.indexOf('#'))
                  }
                >
                  Open verification link
                </Link>
              </Button>
            </div>
          )}
          <Button
            variant="outline"
            onClick={() => {
              setReceipt(null)
              setMode('login')
            }}
          >
            Back to sign in
          </Button>
        </section>
      ) : (
        <div className="account-layout">
          <section className="account-card" aria-labelledby="auth-title">
            <div className="account-modes" aria-label="Account access">
              <button
                type="button"
                aria-pressed={mode === 'login'}
                disabled={auth.busy}
                onClick={() => {
                  setMode('login')
                  setIssue('')
                  setPassword('')
                }}
              >
                Sign in
              </button>
              <button
                type="button"
                aria-pressed={mode === 'register'}
                disabled={auth.busy}
                onClick={() => {
                  setMode('register')
                  setIssue('')
                  setPassword('')
                }}
              >
                Create account
              </button>
            </div>
            <h2 id="auth-title">
              {mode === 'login' ? 'Sign in' : 'Create account'}
            </h2>
            {verified && (
              <p className="account-success" role="status">
                <CheckCircle2 size={18} aria-hidden="true" /> Email verified.
                You can sign in now.
              </p>
            )}
            <form
              className={`account-form account-form--${mode}`}
              onSubmit={(event) => void submit(event)}
              noValidate
            >
              <div>
                <label htmlFor="account-username">Username</label>
                <input
                  id="account-username"
                  name="username"
                  autoComplete="username"
                  autoCapitalize="none"
                  spellCheck={false}
                  maxLength={32}
                  value={username}
                  disabled={auth.busy}
                  aria-invalid={Boolean(error)}
                  aria-describedby={error ? 'account-error' : 'username-hint'}
                  onChange={(event) => {
                    setUsername(event.target.value)
                    setIssue('')
                  }}
                />
                <small id="username-hint">
                  3–32 letters, numbers, dots, hyphens or underscores.
                </small>
              </div>
              {mode === 'register' && (
                <div>
                  <label htmlFor="account-email">Email address</label>
                  <input
                    id="account-email"
                    name="email"
                    type="email"
                    autoComplete="email"
                    autoCapitalize="none"
                    spellCheck={false}
                    required
                    maxLength={254}
                    value={email}
                    disabled={auth.busy}
                    aria-invalid={Boolean(error)}
                    aria-describedby={error ? 'account-error' : 'email-hint'}
                    onChange={(event) => {
                      setEmail(event.target.value)
                      setIssue('')
                    }}
                  />
                  <small id="email-hint">
                    Verify your email before signing in.
                  </small>
                </div>
              )}
              <div>
                <label htmlFor="account-password">Password</label>
                <div className="account-password">
                  <input
                    id="account-password"
                    name="password"
                    type={visible ? 'text' : 'password'}
                    autoComplete={
                      mode === 'register' ? 'new-password' : 'current-password'
                    }
                    minLength={6}
                    maxLength={128}
                    value={password}
                    disabled={auth.busy}
                    aria-invalid={Boolean(error)}
                    aria-describedby={error ? 'account-error' : 'password-hint'}
                    onChange={(event) => {
                      setPassword(event.target.value)
                      setIssue('')
                    }}
                  />
                  <button
                    type="button"
                    aria-label={visible ? 'Hide password' : 'Show password'}
                    aria-pressed={visible}
                    onClick={() => setVisible((value) => !value)}
                  >
                    {visible ? (
                      <EyeOff size={20} aria-hidden="true" />
                    ) : (
                      <Eye size={20} aria-hidden="true" />
                    )}
                  </button>
                </div>
                <small id="password-hint">6–128 characters.</small>
              </div>
              {error && (
                <p
                  id="account-error"
                  role="alert"
                  className="collection-form-error"
                >
                  {error}
                </p>
              )}
              <Button type="submit" disabled={auth.busy}>
                {auth.busy
                  ? 'Please wait…'
                  : mode === 'login'
                    ? 'Sign in'
                    : 'Create account'}
              </Button>
              {mode === 'login' && auth.error.includes('Verify your email') && (
                <Button
                  type="button"
                  variant="outline"
                  disabled={auth.busy}
                  onClick={async () => {
                    const result = await auth.resend(username.trim(), password)
                    if (result) {
                      setReceipt(result)
                      setPassword('')
                    }
                  }}
                >
                  Resend verification link
                </Button>
              )}
            </form>
          </section>
        </div>
      )}
    </div>
  )
}
