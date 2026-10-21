import { test, expect } from './fixtures'

const arrival = { id: 329865, title: 'Arrival', year: 2016, runtime_minutes: 116, language: 'English', genres: ['Science Fiction','Drama'], director: 'Denis Villeneuve', cast: ['Amy Adams'], overview: 'A linguist communicates with visitors.', tagline: '', cover_url: '/covers/329865.svg', source: 'demo', artwork_kind: 'illustration' }
const response = { items: [arrival], total: 1, indexed_movies: 200, data_source: 'demo', limited: true, page: 1, page_size: 20, total_pages: 1, match_type: 'keyword' }

test('single search supports immediate submission, keeps filters and opens a movie tile', async ({ page }) => {
  const requests: URLSearchParams[] = []
  await page.route('**/api/search/catalog*', route => {
    const params = new URL(route.request().url()).searchParams
    if (!params.get('q')) return route.continue()
    requests.push(params)
    return route.fulfill({ json: response })
  })
  await page.goto('/')
  await expect(page.getByRole('searchbox')).toHaveCount(1)
  await expect(page.getByRole('button', { name: 'Mood or story' })).toHaveCount(0)
  await page.getByLabel('Find your next film').fill('Aliens and communication')
  expect(requests).toHaveLength(0)
  await page.getByLabel('Maximum runtime').selectOption('120')
  await page.getByLabel('Language', { exact: true }).selectOption('English')
  await page.getByRole('button', { name: 'Search', exact: true }).click()
  await expect.poll(() => requests.length).toBeGreaterThan(0)
  expect(requests[0].get('q')).toBe('Aliens and communication')
  expect(requests[0].get('max_runtime')).toBe('120')
  expect(requests[0].get('language')).toBe('English')
  await expect(page.locator('.results-line').getByRole('status')).toContainText('1 result matching')
  await expect(page.locator('.collection-endnote')).toHaveCount(0)
  await expect(page.locator('.collection-note')).toHaveCount(0)
  await page.getByRole('link', { name: 'Explore Arrival', exact: true }).click()
  await expect(page).toHaveURL(/movies\/329865/)
})

test('old meaning URLs migrate, failures retry and unsupported searches stay empty', async ({ page }) => {
  let fail = true
  await page.route('**/api/search/catalog*', route => fail ? route.fulfill({ status: 503, json: { detail: 'secret' } }) : route.fulfill({ json: { ...response, items: [], total: 0, total_pages: 0 } }))
  await page.goto('/?mode=meaning&q=romance&language=Japanese')
  await expect(page).not.toHaveURL(/mode=/)
  await expect(page.getByRole('alert')).toBeVisible()
  await expect(page.getByRole('alert')).not.toContainText('secret')
  fail = false
  await page.getByRole('button', { name: 'Try again', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'No films found just yet.' })).toBeVisible()
  await expect(page.getByRole('searchbox')).toHaveValue('romance')
  await expect(page.getByLabel('Language', { exact: true })).toHaveValue('Japanese')
})

test('romance has an honest empty state in the offline catalog', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/?q=romance')
  await expect(page.getByRole('heading', { name: 'No films found just yet.' })).toBeVisible()
  await expect(page.locator('.movie-card')).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()
  await page.getByRole('button', { name: 'Show all films' }).click()
  await expect(page.locator('.movie-card')).toHaveCount(10)
})

test('server pagination preserves filters, supports back and resets on a new search', async ({ page }) => {
  await page.route('**/api/search/catalog*', route => {
    const params = new URL(route.request().url()).searchParams
    const pageNumber = Number(params.get('page') || 1)
    const items = Array.from({ length: pageNumber === 3 ? 5 : 20 }, (_, i) => ({ ...arrival, id: 10000 + (pageNumber - 1) * 20 + i, title: `Film ${(pageNumber - 1) * 20 + i + 1}` }))
    return route.fulfill({ json: { ...response, items, total: 45, total_pages: 3, page: pageNumber } })
  })
  await page.goto('/?q=romance&language=English')
  await expect(page.getByText('Page 1 of 3')).toBeVisible()
  await expect(page.locator('.results-line').getByRole('status')).toContainText('20 results')
  await expect(page.getByRole('button', { name: 'Previous', exact: true })).toBeDisabled()
  await page.getByRole('button', { name: 'Next', exact: true }).click()
  await expect(page).toHaveURL(/page=2/)
  await expect(page.getByText('Page 2 of 3')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Film 21', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Film 1', exact: true })).toHaveCount(0)
  await expect(page.getByRole('searchbox')).toHaveValue('romance')
  await expect(page.getByLabel('Language', { exact: true })).toHaveValue('English')
  await page.getByRole('button', { name: 'Next', exact: true }).click()
  await expect(page.locator('.movie-card')).toHaveCount(5)
  await expect(page.locator('.results-line').getByRole('status')).toContainText('5 results')
  await expect(page.getByRole('button', { name: 'Next', exact: true })).toBeDisabled()
  await page.goBack()
  await expect(page.getByText('Page 2 of 3')).toBeVisible()
  await page.getByRole('searchbox').fill('Amy Adams')
  await page.getByRole('button', { name: 'Search', exact: true }).click()
  await expect(page).not.toHaveURL(/page=/)
  await expect(page.getByText('Page 1 of 3')).toBeVisible()
})

test('genre results label cards with the matching genre', async ({ page }) => {
  await page.route('**/api/search/catalog*', route => route.fulfill({ json: { ...response, applied_genres: ['Romance'], match_type: 'genre', items: [{ ...arrival, genres: ['Science Fiction', 'Romance'] }] } }))
  await page.goto('/?q=romance')
  await expect(page.getByText('Matching Romance films.', { exact: true })).toBeVisible()
  await expect(page.locator('.movie-card .movie-meta')).toContainText('Romance')
})
