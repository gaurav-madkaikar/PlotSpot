import { useEffect, useId, useRef, type ReactNode } from 'react'
import { X } from 'lucide-react'
import { Button } from './ui/button'

export function CollectionDialog({
  title,
  eyebrow = 'YOUR COLLECTIONS',
  busy = false,
  description,
  onClose,
  children,
}: {
  title: string
  eyebrow?: string
  busy?: boolean
  description: string
  onClose: () => void
  children: ReactNode
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const opener = useRef<HTMLElement | null>(null)
  const titleId = useId()
  const descriptionId = useId()
  useEffect(() => {
    const element = dialog.current
    if (!opener.current && document.activeElement instanceof HTMLElement)
      opener.current = document.activeElement
    element?.showModal()
    return () => {
      element?.close()
      // The picker unmounts on Done, so restore focus explicitly as well.
      const target = opener.current?.isConnected
        ? opener.current
        : document.getElementById('main-content')
      target?.focus({ preventScroll: true })
    }
  }, [])
  return (
    <dialog
      ref={dialog}
      className="collection-dialog"
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
      onCancel={(event) => {
        if (busy) event.preventDefault()
        else onClose()
      }}
      onClose={() => {
        if (!dialog.current?.open) onClose()
      }}
    >
      <header>
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h2 id={titleId}>{title}</h2>
        </div>
        <Button
          variant="ghost"
          type="button"
          disabled={busy}
          aria-label={
            eyebrow === 'YOUR COLLECTIONS'
              ? 'Close collection dialog'
              : 'Close discussion dialog'
          }
          onClick={() => dialog.current?.close()}
        >
          <X size={20} aria-hidden="true" />
        </Button>
      </header>
      <p id={descriptionId} className="collection-dialog-description">
        {description}
      </p>
      {children}
    </dialog>
  )
}
