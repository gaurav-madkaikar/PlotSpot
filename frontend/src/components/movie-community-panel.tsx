import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { MessageCircle, Pencil, Trash2, Flag } from 'lucide-react'
import { useAuth } from '../lib/auth'
import { AccountApiError } from '../lib/account-api'
import * as api from '../lib/community-api'
import type {
  CommunityPost,
  PostDraft,
  PostKind,
} from '../lib/community-contracts'
import { CommunityPostForm } from './community-post-form'
import { CommunityPostDialog, type PostAction } from './community-post-dialog'
import { CommunityReportPanel } from './community-report-panel'
import { Button } from './ui/button'
function Post({
  post,
  kind,
  onAction,
  onReply,
}: {
  post: CommunityPost
  kind: PostKind
  onAction: (target: PostAction) => void
  onReply?: () => void
}) {
  return (
    <article
      className="community-post"
      style={{ '--reply-depth': post.depth } as React.CSSProperties}
    >
      <div className="community-post-heading">
        <p className="community-meta">
          {post.author}{' '}
          <time dateTime={post.created_at}>
            {new Date(post.created_at).toLocaleDateString(undefined, {
              month: 'short',
              day: 'numeric',
              year: 'numeric',
            })}
          </time>
          {post.spoilers && (
            <span className="community-spoiler-badge">Spoilers</span>
          )}
          {post.parent_id && <span>Nested reply</span>}
        </p>
        <div className="community-post-actions">
          {post.can_edit && (
            <Button
              variant="ghost"
              aria-label="Edit post"
              onClick={() => onAction({ post, kind, action: 'edit' })}
            >
              <Pencil size={18} aria-hidden="true" />
            </Button>
          )}
          {post.can_delete && (
            <Button
              variant="ghost"
              aria-label="Remove post"
              onClick={() => onAction({ post, kind, action: 'delete' })}
            >
              <Trash2 size={18} aria-hidden="true" />
            </Button>
          )}
          {!post.can_delete && !post.removed && (
            <Button
              variant="ghost"
              aria-label="Report post"
              onClick={() => onAction({ post, kind, action: 'report' })}
            >
              <Flag size={18} aria-hidden="true" />
            </Button>
          )}
        </div>
      </div>
      {post.title && <h3>{post.title}</h3>}
      <p className="community-body">
        {post.removed
          ? 'This post was removed.'
          : post.spoiler_locked
            ? 'Enable spoilers to read this conversation.'
            : post.body}
      </p>
      {onReply && !post.removed && !post.spoiler_locked && post.depth < 3 && (
        <Button variant="ghost" onClick={onReply}>
          Reply
        </Button>
      )}
    </article>
  )
}
export function MovieCommunityPanel({
  movieId,
  allowSpoilers,
}: {
  movieId: number
  allowSpoilers: boolean
}) {
  const auth = useAuth()
  const owner = auth.user!.id
  const client = useQueryClient()
  const mounted = useRef(false)
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<number | null>(null)
  const [replyPage, setReplyPage] = useState(1)
  const [compose, setCompose] = useState<'thread' | 'reply' | null>(null)
  const [parent, setParent] = useState<CommunityPost | null>(null)
  const [target, setTarget] = useState<PostAction | null>(null)
  const [busy, setBusy] = useState(false)
  const locked = useRef(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const key = useRef(crypto.randomUUID())
  const original = useRef('')
  const threads = useQuery({
    queryKey: ['community-threads', owner, movieId, allowSpoilers, page],
    queryFn: ({ signal }) =>
      api.loadThreads(owner, movieId, page, allowSpoilers, signal),
    gcTime: 0,
    retry: false,
  })
  const detail = useQuery({
    queryKey: ['community-thread', owner, selected, allowSpoilers],
    queryFn: ({ signal }) =>
      api.loadThread(owner, selected!, allowSpoilers, signal),
    enabled: selected !== null,
    gcTime: 0,
    retry: false,
  })
  const replies = useQuery({
    queryKey: ['community-replies', owner, selected, allowSpoilers, replyPage],
    queryFn: ({ signal }) =>
      api.loadReplies(owner, selected!, replyPage, allowSpoilers, signal),
    enabled: selected !== null,
    gcTime: 0,
    retry: false,
  })
  const caps = useQuery({
    queryKey: ['community-capabilities', owner],
    queryFn: ({ signal }) => api.communityCapabilities(owner, signal),
    gcTime: 0,
    retry: false,
  })
  async function run(operation: () => Promise<unknown>, done: () => void) {
    if (locked.current) return false
    locked.current = true
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await operation()
      if (mounted.current) {
        done()
        await Promise.all(
          ['community-threads', 'community-thread', 'community-replies'].map(
            (name) => client.invalidateQueries({ queryKey: [name, owner] }),
          ),
        )
      }
      return true
    } catch (e) {
      if (mounted.current) {
        setError(
          e instanceof Error ? e.message : 'Your post could not be saved.',
        )
        if (e instanceof AccountApiError && [401, 403].includes(e.status))
          void auth.refresh()
      }
      return false
    } finally {
      locked.current = false
      if (mounted.current) setBusy(false)
    }
  }
  function openCompose(
    type: 'thread' | 'reply',
    post: CommunityPost | null = null,
  ) {
    setCompose(type)
    setParent(post)
    setError('')
    key.current = crypto.randomUUID()
    original.current = ''
  }
  async function submit(draft: PostDraft) {
    const value = JSON.stringify({ draft, parent: parent?.id ?? null })
    if (original.current && original.current !== value)
      key.current = crypto.randomUUID()
    original.current = value
    return run(
      () =>
        compose === 'thread'
          ? api.createThread(owner, movieId, draft, key.current, auth.csrf)
          : api.createReply(
              owner,
              selected!,
              draft,
              parent?.id ?? null,
              key.current,
              auth.csrf,
            ),
      () => {
        setCompose(null)
        setNotice('Your post was added.')
        setPage(1)
      },
    )
  }
  function actions(t: PostAction) {
    setError('')
    setTarget(t)
  }
  const thread = detail.data?.thread
  return (
    <section
      className="question-panel community-panel"
      aria-label="Movie community"
    >
      <div className="community-heading">
        <div>
          <p className="eyebrow">COMMUNITY</p>
          <h2>Join the conversation</h2>
          <p>
            Share your take on the film. Mark story and ending details as
            spoilers.
          </p>
        </div>
        <Button disabled={busy} onClick={() => openCompose('thread')}>
          <MessageCircle size={18} aria-hidden="true" />
          Start a discussion
        </Button>
      </div>
      {notice && (
        <p role="status" className="community-notice">
          {notice}
        </p>
      )}
      {error && !target && (
        <p role="alert" className="collection-form-error">
          {error}
        </p>
      )}
      {compose === 'thread' && (
        <CommunityPostForm
          thread
          label="Post discussion"
          busy={busy}
          onSubmit={submit}
          onCancel={() => setCompose(null)}
        />
      )}
      {selected === null ? (
        <>
          {threads.isPending ? (
            <p role="status">Loading conversations…</p>
          ) : threads.isError ? (
            <p role="alert">
              Conversations could not be loaded.{' '}
              <Button variant="ghost" onClick={() => void threads.refetch()}>
                Retry
              </Button>
            </p>
          ) : (
            <>
              {threads.data.items.map((post) => (
                <div className="community-thread-preview" key={post.id}>
                  <Button
                    variant="ghost"
                    className="community-thread-link"
                    onClick={() => {
                      setSelected(post.id)
                      setReplyPage(1)
                      setCompose(null)
                      setError('')
                    }}
                  >
                    <span>{post.title}</span>
                  </Button>
                  <p className="community-meta">
                    {post.author} · {post.replies} replies
                    {post.spoilers && ' · Spoilers'}
                  </p>
                </div>
              ))}
              {!threads.data.items.length && (
                <div className="community-empty">
                  <MessageCircle size={28} aria-hidden="true" />
                  <h3>What stayed with you?</h3>
                  <p>Start the first conversation about this film.</p>
                </div>
              )}
              {(page > 1 || threads.data.has_more) && (
                <div className="community-pagination">
                  <Button
                    variant="ghost"
                    disabled={page === 1}
                    onClick={() => setPage((p) => p - 1)}
                  >
                    Previous
                  </Button>
                  <span>Page {page}</span>
                  <Button
                    variant="ghost"
                    disabled={!threads.data.has_more}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Next
                  </Button>
                </div>
              )}
            </>
          )}
        </>
      ) : (
        <div className="community-conversation">
          <Button
            variant="ghost"
            onClick={() => {
              setSelected(null)
              setCompose(null)
              setError('')
            }}
          >
            All discussions
          </Button>
          {detail.isPending ? (
            <p role="status">Loading discussion…</p>
          ) : detail.isError ? (
            <p role="alert">
              This discussion could not be loaded.{' '}
              <Button variant="ghost" onClick={() => void detail.refetch()}>
                Retry
              </Button>
            </p>
          ) : (
            thread && (
              <>
                <Post post={thread} kind="thread" onAction={actions} />
                {!thread.spoiler_locked && (
                  <Button
                    variant="outline"
                    disabled={busy}
                    onClick={() => openCompose('reply')}
                  >
                    Reply to discussion
                  </Button>
                )}
                {compose === 'reply' && (
                  <div className="community-reply-form">
                    {parent && (
                      <p className="community-meta">
                        Replying to {parent.author}
                      </p>
                    )}
                    <CommunityPostForm
                      key={parent?.id ?? 'root'}
                      initial={{
                        body: '',
                        spoilers: thread.spoilers || !!parent?.spoilers,
                      }}
                      label="Post reply"
                      busy={busy}
                      onSubmit={submit}
                      onCancel={() => setCompose(null)}
                    />
                  </div>
                )}
                {replies.isPending ? (
                  <p role="status">Loading replies…</p>
                ) : replies.isError ? (
                  <p role="alert">
                    Replies could not be loaded.{' '}
                    <Button
                      variant="ghost"
                      onClick={() => void replies.refetch()}
                    >
                      Retry
                    </Button>
                  </p>
                ) : (
                  <>
                    {replies.data.items.map((post) => (
                      <Post
                        key={post.id}
                        post={post}
                        kind="reply"
                        onAction={actions}
                        onReply={() => openCompose('reply', post)}
                      />
                    ))}
                    {!replies.data.items.length && (
                      <p className="community-meta">No replies yet.</p>
                    )}
                    {(replyPage > 1 || replies.data.has_more) && (
                      <div className="community-pagination">
                        <Button
                          variant="ghost"
                          disabled={replyPage === 1}
                          onClick={() => setReplyPage((p) => p - 1)}
                        >
                          Previous replies
                        </Button>
                        <span>Page {replyPage}</span>
                        <Button
                          variant="ghost"
                          disabled={!replies.data.has_more}
                          onClick={() => setReplyPage((p) => p + 1)}
                        >
                          Next replies
                        </Button>
                      </div>
                    )}
                  </>
                )}
              </>
            )
          )}
        </div>
      )}
      {caps.data?.moderator && (
        <CommunityReportPanel owner={owner} allowed={allowSpoilers} />
      )}
      {target && (
        <CommunityPostDialog
          target={target}
          busy={busy}
          error={error}
          onClose={() => setTarget(null)}
          onEdit={(draft) =>
            run(
              () =>
                api.editPost(
                  owner,
                  target.kind,
                  target.post.id,
                  draft,
                  target.post.revision,
                  auth.csrf,
                ),
              () => {
                setTarget(null)
                setNotice('Your post was updated.')
                setError('')
              },
            )
          }
          onDelete={() =>
            void run(
              () =>
                api.deletePost(
                  owner,
                  target.kind,
                  target.post.id,
                  target.post.revision,
                  auth.csrf,
                ),
              () => {
                if (target.kind === 'thread') {
                  setSelected(null)
                  setCompose(null)
                }
                setTarget(null)
                setNotice('Your post was removed.')
              },
            )
          }
          onReport={(reason, details) =>
            void run(
              () =>
                api.reportPost(
                  owner,
                  target.kind,
                  target.post.id,
                  reason,
                  details,
                  auth.csrf,
                ),
              () => {
                setTarget(null)
                setNotice('Report sent for moderator review.')
              },
            )
          }
        />
      )}
    </section>
  )
}
