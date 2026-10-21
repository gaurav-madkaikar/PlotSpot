import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, useLocation } from 'react-router'

const sections = [
  ['about', 'About'],
  ['facts', 'Facts'],
  ['quiz', 'Quiz'],
  ['discuss', 'Discuss'],
] as const

export function MovieSectionNavigation() {
  const { hash, state, key } = useLocation()
  const [active, setActive] = useState('about')
  useEffect(() => {
    const update = () => {
      const passed = sections.filter(([id]) => {
        const element = document.getElementById(id)
        return element && element.getBoundingClientRect().top <= 130
      })
      setActive(passed.at(-1)?.[0] ?? 'about')
    }
    update()
    window.addEventListener('scroll', update, { passive: true })
    return () => window.removeEventListener('scroll', update)
  }, [])
  useEffect(() => {
    const id = hash.slice(1)
    if (
      !sections.some(([key]) => key === id) &&
      !['cast', 'watch', 'related'].includes(id)
    )
      return
    const frame = requestAnimationFrame(() => {
      document.getElementById(id)?.scrollIntoView({ block: 'start' })
      if (sections.some(([key]) => key === id)) setActive(id)
    })
    return () => cancelAnimationFrame(frame)
  }, [hash, key])
  return (
    <nav className="movie-section-nav" aria-label="Movie sections">
      {sections.map(([id, label]) => (
        <Link
          key={id}
          to={`#${id}`}
          state={state}
          preventScrollReset
          aria-current={active === id ? 'location' : undefined}
        >
          {label}
        </Link>
      ))}
    </nav>
  )
}

// Once visited, keep the panel mounted so navigating never discards user input.
export function MovieFeatureSection({
  id,
  title,
  children,
}: {
  id: string
  title: string
  children: ReactNode
}) {
  const ref = useRef<HTMLElement>(null)
  const { hash } = useLocation()
  const [visited, setVisited] = useState(false)
  const requested = hash === `#${id}`
  useEffect(() => {
    if (requested) setVisited(true)
  }, [requested])
  useEffect(() => {
    if (visited || !ref.current) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisited(true)
          observer.disconnect()
        }
      },
      { rootMargin: '160px 0px' },
    )
    observer.observe(ref.current)
    return () => observer.disconnect()
  }, [visited])
  return (
    <section
      id={id}
      ref={ref}
      className="movie-feature-section"
      aria-label={title}
    >
      {(visited || requested) && children ? (
        children
      ) : (
        <div className="movie-feature-placeholder">
          <h2>{title}</h2>
          <p>Explore this section below.</p>
        </div>
      )}
    </section>
  )
}
