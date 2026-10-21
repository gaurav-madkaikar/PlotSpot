import { ArrowUpRight, Film, MessageCircle, ShieldCheck } from 'lucide-react'
import { Link } from 'react-router'

export function AboutPage() {
  return (
    <div className="page-width about-page">
      <p className="eyebrow">WELCOME TO PLOTSPOT</p>
      <h1>
        For the film.
        <br />
        <span>And everything after.</span>
      </h1>
      <p className="page-intro">
        A movie companion for curious viewers, growing one thoughtful feature at
        a time.
      </p>
      <div className="about-grid">
        <section>
          <Film size={24} aria-hidden="true" />
          <h2>Discover your next film.</h2>
          <p>
            Find films by title, actor, genre or story in one search. Explore a
            saved 200-film TMDB collection or the offline demo, refine your
            results, and save something for later.
          </p>
        </section>
        <section>
          <MessageCircle size={24} aria-hidden="true" />
          <h2>Stay for the conversation.</h2>
          <p>
            Ask questions with cited evidence across ten starter films.
            Interstellar also has saved production facts and a story quiz. More
            collections, live news and community threads will follow.
          </p>
        </section>
        <section>
          <ShieldCheck size={24} aria-hidden="true" />
          <h2>Know what you’re reading.</h2>
          <p>
            Demo mode uses authored sample text and original illustrations. Live
            mode identifies movie details and posters from TMDB. Sign in to keep
            collections and spoiler preferences in your account.
          </p>
        </section>
      </div>
      <div className="about-note">
        <h2>A learning project with a clear next step.</h2>
        <p>
          Search uses known titles and cast, genre constraints and
          synopsis-based matches. Coverage is limited to the saved collection.
          Broader evidence, better story ranking and parallel agents are the
          next steps.
        </p>
        <Link className="text-link" to="/">
          Back to the collection <ArrowUpRight size={16} aria-hidden="true" />
        </Link>
      </div>
      <section className="about-note" aria-label="TMDB attribution">
        <a href="https://www.themoviedb.org" target="_blank" rel="noreferrer">
          <img
            className="tmdb-logo"
            src="https://www.themoviedb.org/assets/2/v4/logos/v2/blue_square_2-d537fb228cf3ded904ef09b136fe3fec72548ebc1fea3fbbd1ad9e36364db38b.svg"
            alt="The Movie Database (TMDB)"
            width="96"
            height="69"
          />
        </a>
        <p>
          This product uses the TMDB API but is not endorsed or certified by
          TMDB.
        </p>
      </section>
    </div>
  )
}
