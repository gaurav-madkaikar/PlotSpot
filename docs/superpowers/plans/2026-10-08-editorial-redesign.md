# Frame editorial redesign

Requested by the user while they implement vector math. Apply ui-ux-pro-max to a coherent visual revamp of the existing working frontend.

## Direction and scope

Use an independent cinema magazine aesthetic: warm cream, ink, vermilion, oversized serif/sans typography, a programme-style illustrated feature, numbered section captions, strong rules, and generous poster grids. Retain existing navigation, title/cast search, URL filters, typo suggestions, save controls, spoiler preference, and truthful feature availability. The learner's backend exercise and tests are outside this change.

The skill's Magazine Style typography result supports the serif/sans pairing. Generic funnel layouts and purple palettes do not fit this product and are not adopted. Alternative streaming-style dark tiles would resemble the existing design; heavy animated 3D would add complexity without helping movie discovery. The editorial direction meets the user's request for a distinctive redesign with a lightweight implementation.

## Implementation and verification

- [x] Bundle Libre Bodoni locally alongside existing Inter.
- [x] Recompose the discovery hero and shared header/footer; preserve semantic links and accessible names.
- [x] Replace the visual tokens and component styles coherently across discovery, details, collection, about, and recovery states.
- [x] Make search/filter labels visible, preserve 44px controls and contrast, and respect reduced motion.
- [x] Run the production build and existing browser suite against isolated demo servers.
- [x] Inspect actual rendered views at 375, 768, 1024, and 1440px, including long titles and landscape; correct overflow and layout defects.
- [x] Record the design decisions and show the refreshed page to the user.

Acceptance: existing browser interactions pass, responsive views have no horizontal overflow, no application errors appear in the browser, and the vector-math files remain untouched.
