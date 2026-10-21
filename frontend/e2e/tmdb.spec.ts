import { test, expect, signInMember } from './fixtures'

const liveMovie = {
  id: 123,
  title: 'Live Example',
  year: null,
  runtime_minutes: null,
  language: 'Korean',
  genres: ['Drama'],
  director: null,
  cast: [],
  overview: '',
  tagline: '',
  cover_url: null,
  source: 'tmdb',
  artwork_kind: 'placeholder',
}

test('live source, unknown metadata, and saved films outside discovery', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.route('**/api/health', (route) =>
    route.fulfill({ json: { status: 'ok', data_source: 'tmdb' } }),
  )
  await page.route('**/api/search/catalog*', (route) =>
    route.fulfill({
      json: {
        items: [liveMovie],
        total: 1,
        data_source: 'tmdb',
        limited: true,
      },
    }),
  )
  await page.route('**/api/movies/123', (route) =>
    route.fulfill({ json: liveMovie }),
  )
  await page.goto('/')
  await expect(page.getByText('Live discovery · TMDB')).toHaveCount(0)
  await expect(
    page.getByText('results are not the complete TMDB catalog.', {
      exact: false,
    }),
  ).toHaveCount(0)
  await expect(
    page.getByRole('img', { name: 'Poster unavailable for Live Example' }),
  ).toBeVisible()
  await page
    .getByRole('button', {
      name: 'Save Live Example to collection',
      exact: true,
    })
    .click()
  await page.getByRole('button', { name: 'Done', exact: true }).click()
  await page
    .getByRole('link', { name: 'Explore Live Example', exact: true })
    .click()
  await expect(
    page.getByRole('heading', { name: 'Live Example', level: 1 }),
  ).toBeVisible()
  await expect(
    page.getByText('Runtime unavailable', { exact: true }),
  ).toBeVisible()
  await expect(
    page.getByText('Director unavailable', { exact: true }),
  ).toBeVisible()
  await expect(
    page.getByText('Overview unavailable.', { exact: true }),
  ).toBeVisible()
  await expect(
    page.getByText('Cast details unavailable.', { exact: true }),
  ).toBeVisible()
  // The saved collection must fetch the ID, not depend on current discovery results.
  await page.unroute('**/api/search/catalog*')
  await page.route('**/api/search/catalog*', (route) =>
    route.fulfill({
      json: { items: [], total: 0, data_source: 'tmdb', limited: true },
    }),
  )
  await page.getByRole('link', { name: /Collections/ }).click()
  await expect(page).toHaveURL(/\/collections$/)
  await expect(
    page.getByRole('link', { name: 'Explore Live Example', exact: true }),
  ).toBeVisible()
  await page.reload()
  await expect(
    page.getByRole('link', { name: 'Explore Live Example', exact: true }),
  ).toHaveCount(0)
  await expect(
    page.getByRole('heading', { name: 'Start your film collection' }),
  ).toBeVisible()
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true)
})

test('a failed poster URL becomes an accessible placeholder', async ({
  page,
}) => {
  await page.route('**/api/movies/123', (route) =>
    route.fulfill({
      json: {
        ...liveMovie,
        cover_url: 'https://image.tmdb.org/t/p/w500/example.jpg',
        artwork_kind: 'poster',
      },
    }),
  )
  await page.route('https://image.tmdb.org/**', (route) => route.abort())
  await page.goto('/movies/123')
  await expect(
    page.getByRole('img', { name: 'Poster unavailable for Live Example' }),
  ).toBeVisible()
})

test('untrusted poster origins are rejected at the UI boundary', async ({
  page,
}) => {
  await page.route('**/api/movies/123', (route) =>
    route.fulfill({
      json: {
        ...liveMovie,
        cover_url: 'https://untrusted.example/tracking.jpg',
        artwork_kind: 'poster',
      },
    }),
  )
  await page.goto('/movies/123')
  await expect(
    page.getByRole('heading', { name: 'The collection is taking a break.' }),
  ).toBeVisible()
})

test('an unavailable saved movie can be removed', async ({ page, baseURL }) => {
  const origin = new URL(baseURL!).origin
  const session = await signInMember(page, origin)
  const saved = await page.request.put('/api/me/collection', {
    headers: { Origin: origin, 'X-CSRF-Token': session.csrf_token },
    data: { revision: 0, saved: [123], watched: [], collections: [] },
  })
  expect(saved.status()).toBe(200)
  await page.route('**/api/movies/123', (route) =>
    route.fulfill({ status: 404, json: { detail: 'Movie unavailable' } }),
  )
  await page.goto('/collections')
  await page
    .getByRole('button', { name: 'Remove unavailable movie #123' })
    .click()
  await expect(
    page.getByRole('heading', { name: 'Start your film collection' }),
  ).toBeVisible()
})
