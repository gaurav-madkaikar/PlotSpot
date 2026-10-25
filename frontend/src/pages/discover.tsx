import { ArrowUpRight } from 'lucide-react'
import { Link } from 'react-router'
import { MovieSearch } from '../components/movie-search'
import { Button } from '../components/ui/button'

export function DiscoverPage() {
  return (
    <div className="page-width discovery-page">
      <div className="edition-line" aria-hidden="true">
        <span>THE PLOTSPOT EDITION</span>
        <span>FILMS. PEOPLE. POSSIBILITIES.</span>
        <span>AN OPEN INVITATION</span>
      </div>
      <section className="discovery-hero" aria-labelledby="discovery-title">
        <div className="hero-copy">
          <h1 id="discovery-title">
            Great films
            <br />
            <span>Better conversations</span>
          </h1>
          <p className="hero-description">
            Some films end, others stay with you.
            <br/>
            Find your next favourite and take a closer look here.
          </p>
          <Button asChild>
            <a href="#collection">
              Explore the collection
            </a>
          </Button>
        </div>
        <Link
          to="/movies/157336"
          className="hero-feature"
          aria-label="Explore featured film Interstellar"
        >
          <div className="hero-feature-top">
            <span>TONIGHT’S FEATURE</span>
            <span>01 / PLOTSPOT</span>
          </div>
          <div className="feature-artwork">
            <img
              src="/covers/157336.svg"
              alt="Original space illustration inspired by Interstellar"
              width="400"
              height="600"
              fetchPriority="high"
            />
            <span className="feature-orbit" aria-hidden="true" />
            <span className="feature-art-caption">BEYOND THE FAMILIAR</span>
            <span className="feature-open" aria-hidden="true">
              <ArrowUpRight size={24} />
            </span>
          </div>
          <div className="hero-feature-copy">
            <p>
              2014 <span> / </span> SCIENCE FICTION
            </p>
            <h2>Interstellar</h2>
            <span>One small step into a much bigger story.</span>
          </div>
        </Link>
      </section>

      <div className="cinema-strip" aria-label="About the PlotSpot experience">
        <span className="strip-title">
          A little less scrolling.
          <br />
          <strong>A little more cinema.</strong>
        </span>
        <span>
          <b>01</b> Find your film
        </span>
        <span>
          <b>02</b> Get a closer look
        </span>
        <span>
          <b>03</b> Keep a favourite
        </span>
        <span>
          <b>04</b> Share your discoveries
        </span>
        <ArrowUpRight size={26} aria-hidden="true" />
      </div>

      <section
        id="collection"
        className="discovery-collection"
        aria-labelledby="collection-title"
      >
        <div className="section-heading">
          <div>
            <p className="eyebrow">
              <span className="section-index">01 /</span> THE DISCOVERY ROOM
            </p>
            <h2 id="collection-title">Follow your curiosity.</h2>
          </div>
        </div>
        <MovieSearch />

      </section>
    </div>
  )
}
