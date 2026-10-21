# Learning note — the Frame visual revamp

The assistant completed this frontend slice while you work on cosine similarity. Your vector-math exercise was not changed.

## How the design reaches the screen

1. `frontend/src/styles.css` declares semantic tokens inside `@theme`: background, surface, text, accent, borders, and fonts. Components reference these roles instead of choosing unrelated colours per page.
2. `frontend/src/main.tsx` imports the local font files. Vite includes them in the application build; users don't need a Google Fonts request to see the typography.
3. `components/shell.tsx` owns shared navigation and the footer. Changing it affects discovery, film details, saved films, and about together.
4. `pages/discover.tsx` composes the hero, search controls, suggestions, and results. The visual markup changed, but its existing API calls, query keys, and URL-backed filter updates remain the same.
5. Media queries in `styles.css` alter grid columns, gutters, headline sizes, and search layout. The data flow remains the same on every device size.

## Why these choices?

**Why two fonts?** Libre Bodoni gives the headings a cinema-magazine identity; Inter keeps forms and movie metadata readable. The hierarchy comes from role, size, spacing, and weight, rather than adding more fonts.

**Why semantic colour tokens?** A colour's role tells us where it belongs. Updating `--color-muted` updates secondary text consistently. It also makes contrast checks tractable: we check actual foreground/background pairs, including the raised panels and dark footer.

**Why native selects?** They preserve keyboard and mobile selection behavior. Styling them costs less complexity than implementing a custom listbox while preserving all its accessibility behavior.

**Why separate the poster link and save button?** Opening a film and saving it are different actions. Nesting a button inside a link creates confusing input behavior; sibling controls keep each action independent.

**Why not put animations everywhere?** Small feedback makes controls responsive; continuous decorative movement competes with film discovery and makes reduced-motion behavior harder to maintain. The app respects `prefers-reduced-motion`.

**Does a visual revamp change backend behavior?** It does not need to. Components still consume the same validated movie objects and call the same API client. A production build checks types and imports, while browser tests check whether the existing user journeys still work.

## Validation

The production build and all 16 existing browser tests passed. Live previews were checked at desktop, tablet, phone, and landscape widths. The development server needed a restart to resolve the newly installed font package; that operational issue did not require changing the API or your exercise.
