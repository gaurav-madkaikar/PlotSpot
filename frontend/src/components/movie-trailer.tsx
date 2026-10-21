import { useRef, useState } from 'react'
import { Play, X } from 'lucide-react'
import type { Movie } from '../lib/contracts'
import { Button } from './ui/button'

type Trailer = NonNullable<NonNullable<Movie['detail_metadata']>['trailer']>

export function MovieTrailer({
  trailer,
  movieTitle,
}: {
  trailer: Trailer
  movieTitle: string
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [playing, setPlaying] = useState(false)
  return (
    <>
      <Button
        variant="outline"
        type="button"
        onClick={() => {
          dialog.current?.showModal()
          setPlaying(true)
        }}
      >
        <Play size={17} aria-hidden="true" />
        Watch trailer
      </Button>
      <dialog
        ref={dialog}
        className="trailer-dialog"
        aria-labelledby="trailer-title"
        aria-describedby="trailer-description"
        onClose={() => setPlaying(false)}
      >
        <header>
          <div>
            <p className="eyebrow">
              {trailer.official ? 'OFFICIAL TRAILER' : 'TRAILER'}
            </p>
            <h2 id="trailer-title">{movieTitle}</h2>
          </div>
          <Button
            variant="ghost"
            type="button"
            aria-label="Close trailer"
            onClick={() => dialog.current?.close()}
          >
            <X size={22} aria-hidden="true" />
          </Button>
        </header>
        {playing && (
          <iframe
            title={`${movieTitle} trailer`}
            src={`https://www.youtube-nocookie.com/embed/${trailer.youtube_key}?autoplay=1`}
            allow="autoplay; encrypted-media; fullscreen; picture-in-picture"
            allowFullScreen
            referrerPolicy="strict-origin-when-cross-origin"
          />
        )}
        <div className="trailer-footer">
          <p id="trailer-description">
            {trailer.name}. Trailers may reveal story details.
          </p>
          <a
            href={`https://www.youtube.com/watch?v=${trailer.youtube_key}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            Watch on YouTube
          </a>
        </div>
      </dialog>
    </>
  )
}
