# PlotSpot — editorial cinema design system

Revamped at the user's request on 2026-10-08 using ui-ux-pro-max. The verified Magazine Style typography result informed the Libre Bodoni / sans pairing. The search tool's generic sales funnel and purple palette did not fit movie discovery; the custom editorial rules below govern the actual implementation.

## Visual direction

An independent cinema programme: warm paper, deep ink, vermilion punctuation, serif headlines and italic emphasis, framed artwork, thin rules, and numbered section captions. Poster imagery provides variety while navigation and controls remain quiet. Avoid streaming-service imitation, ornamental glass panels, fake ratings, excessive motion, and unsupported feature claims.

## Tokens and typography

- Background #F3F0E7, surface #FAF8F2, raised #E7E3D7.
- Foreground / ink #1D2520; secondary text #62645B.
- Accent #B73520; accent hover #932915; on-accent #FFFAF1.
- Divider #D0CEC1; meaningful control boundary #858679.
- On-ink #F3F0E7; on-ink muted #C0C3B5; spotlight highlight #EDC47B.
- Headlines: locally bundled Libre Bodoni regular and italic. Body/UI: existing locally bundled Inter 400/500/600.
- Body base 16px / line height 1.6; small metadata 11–13px. Display headlines scale by breakpoint and wrap naturally.
- Width: 1376px outer maximum, desktop gutters 48px, tablet 32px, mobile 20px.
- Controls use 2–3px corners; save controls and navigation indicators use circles/pills. Posters preserve 2:3 proportions.
- Transitions: 160ms color/opacity, 200ms transform, 260ms image scale. Reduced motion disables animation/transitions. No continuous decorative animation.

## Component composition

- Header: reel SVG, PlotSpot wordmark and labelled route navigation without a saved count.
- Discovery hero: asymmetric headline / dark featured-film programme. Original illustrated Interstellar asset is reused, with a responsive crop that excludes the illustration's printed title.
- Programme strip: three plain descriptive captions, not pretend buttons or an onboarding workflow.
- Search: visible labels, native select elements, comfortable hit targets, immediate URL updates and existing request debounce.
- Posters: four columns on desktop, three on tablet, two on small screens. Save controls always remain visible and independent of the poster link.
- Detail page: paper-framed poster, large title, italic tagline, readable synopsis, spoiler controls, keyboard-operated Radix tabs, numbered cast list, and honest upcoming-feature panels.
- Footer: compact paper surface with product identity, route navigation, copyright and explicit source attribution. Avoid oversized slogans and repeated product descriptors.

## Accessibility and verification

Normal secondary text contrast: 5.28:1 on paper, 4.69:1 on raised surfaces. Accent text on paper: 5.20:1. Control boundary on paper: 3.24:1. Secondary text on ink: 8.76:1. Solid focus rings, semantic links/buttons, visible input labels, skip link, route focus handling, and reduced motion remain in place.

Check 375, 768, 1024, and 1440px plus landscape. Preserve full movie-title wrapping and URL filter state. Do not mask overflow with global clipping. Existing browser tests cover search, suggestions, filtering, saves, back navigation, failures, poster fallback, keyboard tabs, and mobile overflow.

Account access uses a form spanning the content width, aligned with the shared left page gutter with concise headings and no promotional aside. Collections uses one All saved selector label, a count toolbar and an explicit signed-in visit-import notice. Consumer routes use /collections.

Empty collections omit zero counts and refresh notices. Rename/delete actions use 21px icons in 44px accessible buttons beside the selected collection title; visible text labels are omitted. Refresh-lifetime warning copy is removed from consumer UI.

Account access fields use two columns for sign-in and three for registration on large screens; tablet registration uses two columns with a full-width password field, and mobile uses one column. All routes use the dark ink footer with consistent on-ink text, link and focus tokens.

Discovery adds Minimum rating alongside genre, runtime and language. Search and four filters share one desktop row; tablet uses two filter columns and narrow mobile stacks. Movie previews use a shared star/one-decimal/TMDB badge with accessible vote-count attribution and truthful unrated/unavailable states.

Discovery uses a compact labelled Sort by control on the results row: Best rated (default) or Highest score. The original search/four-filter toolbar stays intact. Preview badges retain original TMDB scores and expose compact vote counts with exact counts in accessible labels and hover titles.

Signed-in account uses a full-width two-column collection summary / Viewing preferences layout, stacking below 900px. Settings use labelled native checkbox switches, shared accent/focus tokens, concise helper text and Save/Reset with inline status/error/conflict feedback. Guest access form and dark footer remain unchanged.

Account history spans the account grid beneath preferences, with quiet Recently viewed/Quiz history toggle buttons, compact poster/title/date rows, score summaries and native pagination. Empty states omit counts; independent clear actions use an inline two-step confirmation. Save movie-page history uses the existing labelled switch styling. Preserve focus indicators, dark footer and mobile wrapping.
