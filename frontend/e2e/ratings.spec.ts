import { test, expect } from './fixtures'
const films = [
  { id: 1, title: 'Alpha Film', vote_average: 7.4, vote_count: 100 },
  { id: 2, title: 'Bravo Film', vote_average: 9.1, vote_count: 200 },
  { id: 3, title: 'Charlie Film', vote_average: 8.2, vote_count: 300 },
  { id: 4, title: 'Unrated Film', vote_average: 0, vote_count: 0 },
  { id: 5, title: 'Unknown Film', vote_average: null, vote_count: null },
  { id: 6, title: 'Tiny Vote Film', vote_average: 10, vote_count: 2 },
].map((movie) => ({
  ...movie,
  year: 2020,
  runtime_minutes: 100,
  language: 'English',
  genres: ['Drama'],
  cast: [],
  director: null,
  overview: 'A film story.',
  tagline: '',
  cover_url: null,
  source: 'tmdb',
  artwork_kind: 'placeholder',
}))
async function mockSearch(page: import('@playwright/test').Page) {
  await page.route('**/api/search/catalog*', (route) => {
    const params = new URL(route.request().url()).searchParams
    const threshold = params.get('min_rating')
    const items = films.filter(
      (m) =>
        threshold === null ||
        (m.vote_count != null &&
          m.vote_count > 0 &&
          m.vote_average != null &&
          m.vote_average >= Number(threshold)),
    )
    const order =
      params.get('sort_by') === 'rating'
        ? [6, 2, 3, 1, 4, 5]
        : [2, 3, 1, 6, 4, 5]
    items.sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id))
    return route.fulfill({
      json: {
        items,
        total: items.length,
        page: 1,
        page_size: 20,
        total_pages: 1,
        data_source: 'tmdb',
        match_type: 'browse',
      },
    })
  })
  await page.route('**/api/search/suggestions*', (r) =>
    r.fulfill({ json: { items: [], indexed_movies: 5, limited: true } }),
  )
}

test('ratings appear on previews and minimum selection resets pagination and survives typing', async ({
  page,
}) => {
  await mockSearch(page)
  await page.goto('/?page=2&search_token=' + 'a'.repeat(32))
  await expect(page.locator('.movie-card').first()).toContainText('Bravo Film')
  await expect(page.locator('.movie-preview-rating').first()).toHaveAttribute(
    'aria-label',
    'TMDB rating 9.1 out of 10 from 200 votes',
  )
  await expect(page.getByText('Not rated', { exact: true })).toBeVisible()
  await expect(
    page.getByText('Rating unavailable', { exact: true }),
  ).toBeVisible()
  await page.getByLabel('Minimum rating').selectOption('8')
  await expect(page).toHaveURL(/min_rating=8/)
  expect(new URL(page.url()).searchParams.has('page')).toBe(false)
  expect(new URL(page.url()).searchParams.has('search_token')).toBe(false)
  await expect(page.locator('.movie-card')).toHaveCount(3)
  await page.getByRole('searchbox').fill('film')
  await expect(page).toHaveURL(/q=film/)
  expect(new URL(page.url()).searchParams.get('min_rating')).toBe('8')
  await page.getByRole('button', { name: 'Clear filters', exact: true }).click()
  await expect(page.getByLabel('Minimum rating')).toHaveValue('')
  await expect(page.locator('.movie-card')).toHaveCount(6)
})

for (const width of [1440, 900, 375])
  test(`rating controls and previews fit at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 950 })
    await mockSearch(page)
    await page.goto('/?min_rating=8')
    await expect(page.locator('.movie-card')).toHaveCount(3)
    const filters = [
      page.getByRole('searchbox'),
      page.getByLabel('Genre', { exact: true }),
      page.getByLabel('Maximum runtime'),
      page.getByLabel('Language', { exact: true }),
      page.getByLabel('Minimum rating'),
    ]
    if (width >= 1100) {
      const boxes = await Promise.all(
        filters.map((f) => f.locator('..').boundingBox()),
      )
      expect(boxes.every((b) => Math.abs(b!.y - boxes[0]!.y) < 2)).toBe(true)
    }
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true)
    await page.getByLabel('Minimum rating').focus()
    const style = await page.getByLabel('Minimum rating').evaluate((el) => ({
      radius: getComputedStyle(el.parentElement!).borderRadius,
      shadow: getComputedStyle(el.parentElement!).boxShadow,
    }))
    expect(style.radius).toBe('12px')
    expect(style.shadow).toContain('inset')
  })

test('related movie tiles use the same attributed rating badge', async ({
  page,
}) => {
  await page.route('**/api/movies/27205/related', (r) =>
    r.fulfill({
      json: {
        movie_id: 27205,
        checked_at: '2026-10-12T00:00:00Z',
        stale: false,
        items: [
          {
            id: 2,
            title: 'Related Film',
            year: 2020,
            adult: false,
            poster_url: null,
            vote_average: 8.7,
            vote_count: 50,
          },
        ],
      },
    }),
  )
  await page.goto('/movies/27205#related')
  await expect(
    page.locator('.related-tile .movie-preview-rating'),
  ).toHaveAttribute('aria-label', 'TMDB rating 8.7 out of 10 from 50 votes')
})

test('vote-aware order is explicit, raw order remains available and clear preserves it', async ({
  page,
}) => {
  await mockSearch(page)
  await page.goto('/?min_rating=8&page=2&search_token=' + 'b'.repeat(32))
  await expect(page.getByLabel('Sort by')).toHaveValue('trusted')
  await expect(page.locator('.movie-card').first()).toContainText('Bravo Film')
  await expect(
    page
      .locator('.movie-card')
      .filter({ hasText: 'Tiny Vote Film' })
      .locator('.movie-preview-votes'),
  ).toHaveText('2 votes')
  await page.getByLabel('Sort by').selectOption('rating')
  await expect(page.locator('.movie-card').first()).toContainText(
    'Tiny Vote Film',
  )
  await expect(page).toHaveURL(/sort_by=rating/)
  expect(new URL(page.url()).searchParams.has('page')).toBe(false)
  expect(new URL(page.url()).searchParams.has('search_token')).toBe(false)
  expect(new URL(page.url()).searchParams.get('min_rating')).toBe('8')
  await page.getByRole('searchbox').fill('film')
  await expect(page).toHaveURL(/q=film/)
  expect(new URL(page.url()).searchParams.get('sort_by')).toBe('rating')
  await page.getByRole('button', { name: 'Clear filters', exact: true }).click()
  await expect(page.getByLabel('Minimum rating')).toHaveValue('')
  await expect(page.getByLabel('Sort by')).toHaveValue('rating')
  await page.getByLabel('Sort by').selectOption('trusted')
  await expect(page.locator('.movie-card').first()).toContainText('Bravo Film')
})
