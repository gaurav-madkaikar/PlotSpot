# 32. One movie page, progressive loading

The movie page now uses section links rather than tabs. Its header displays the TMDB rating and vote count; cast and production details appear below. Facts, quiz and discussion follow in consistent light sections. The compact spoiler switch controls all three because our current evidence has not been reliably classified as spoiler-free.

## How it connects

`pages/movie.tsx` still loads the movie with TanStack Query and validates the response through the API client. `MovieCast` and `MovieDetails` format that same data; moving the rating into the header requires no extra API call. The cast preview shows six people, expanding to the available twelve credits. It is not the movie's complete cast.

`MovieSectionNavigation` renders real links such as `#quiz`. The URL is shareable and browser back/forward works. It preserves route state so the back link can still return to the user's search or collection. The current section is highlighted using its position in the viewport. Sticky navigation has matching scroll clearance and a visible keyboard focus indicator.

`MovieFeatureSection` uses `IntersectionObserver`: the browser tells us when a section is within 160px of the viewport. At that point we mount its panel. A direct hash link mounts the requested panel immediately. A stable placeholder reserves space beforehand. Mounted panels stay mounted when scrolling elsewhere, preserving quiz answers and discussion drafts.

## Questions and answers

**Does lazy loading regenerate a quiz?** No. Mounting the quiz panel calls its existing GET endpoint for saved content. Only the explicit Generate more questions button calls the generation endpoint.

**Why not load every panel immediately?** A visitor reading the synopsis may never reach the quiz. Deferring panel mounting avoids its unnecessary request. Feature availability remains one small request.

**Does moving between sections erase answers?** No. Tabs used to unmount panels; section links only move the viewport. React state remains in the mounted panel.

**Why erase content when spoilers are disabled?** The panel key includes the spoiler preference. Changing it unmounts the old panel, cancels outstanding work, and discards revealed content and drafts. This prevents stale story details remaining visible after permission is revoked.

**Is hiding spoilers in the UI enough?** No. Existing backend endpoints still check spoiler permission. The frontend preference is only the UI control; validation and permissions remain server responsibilities.

**Does expanding cast fetch more actors?** No. It reveals the structured credits already received. A future complete-cast view would need a separate API contract.

**What did we verify?** Mobile overflow, missing metadata, cast expansion, keyboard links, direct hash loading/reloading, saved-content deferral, quiz progress and discussion draft retention, preference changes, and existing browser journeys. Provider additions such as trailers and watch availability are separate phases.
