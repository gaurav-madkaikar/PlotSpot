# 24. Safe cached results and responsive search controls

## Why the search crashed

The API added `applied_genres`, but React Query could still hold an older response without that field during a development hot update. Reading `undefined.length` crashed the component. Zod supplies defaults for new HTTP responses; it does not revisit objects already in the query cache.

`MovieSearch` now uses `const appliedGenres = data?.applied_genres ?? []` before reading the count, joining names, or choosing the genre on a tile. The regression fixture deliberately seeds an old cache entry without passing through the API parser, so it reproduces the actual compatibility issue.

## Why the recovery screen is separate

The root router's `errorElement` catches unexpected render errors and shows reload and discovery actions. This is a final recovery mechanism. Normal request errors still use the existing retry panel. The recovery screen avoids showing technical exception details.

## How the controls align

A CSS grid places the search group and three filter groups on one desktop row. Below 1050px the search spans the row and the filters share the next row; below 520px each group stacks. `minmax(0, ...)` and `min-width: 0` keep controls from expanding beyond their columns.

Each rounded input wrapper uses `:focus-within` to show an inset accent ring. The native input's outer outline is removed only inside these controls, where the wrapper supplies a visible focus indicator. This avoids a square highlight overflowing the rounded border while preserving keyboard feedback.

## Verification

Browser checks cover old cache compatibility, route recovery, desktop alignment, rounded contained focus rings, and mobile page width. The existing search, filter, pagination, quiz, facts and discussion checks run with them.
