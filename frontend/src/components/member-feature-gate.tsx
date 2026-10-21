import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { LockKeyhole } from 'lucide-react'
import { useAuth } from '../lib/auth'
import { Button } from './ui/button'
export function MemberFeatureGate({
  movieId,
  section,
  children,
}: {
  movieId: number
  section: 'facts' | 'quiz' | 'discuss'
  children: ReactNode
}) {
  const auth = useAuth()
  if (auth.user && auth.status !== 'error') return <>{children}</>
  const title = {
    facts: 'News & facts',
    quiz: 'Story quiz',
    discuss: 'Discussion',
  }[section]
  const target = `/movies/${movieId}#${section}`
  return (
    <div className="question-panel member-feature-gate">
      <LockKeyhole size={24} aria-hidden="true" />
      <div>
        <p className="eyebrow">MEMBERS</p>
        <h2>{title}</h2>
        <p>
          Sign in to explore{' '}
          {section === 'discuss'
            ? 'film conversations and source-backed answers'
            : section === 'quiz'
              ? 'the story quiz'
              : 'movie facts'}
          .
        </p>
      </div>
      {auth.status === 'checking' ? (
        <p role="status">Checking your account…</p>
      ) : (
        <Button asChild>
          <Link to={`/account?returnTo=${encodeURIComponent(target)}`}>
            Sign in or create an account
          </Link>
        </Button>
      )}
    </div>
  )
}
