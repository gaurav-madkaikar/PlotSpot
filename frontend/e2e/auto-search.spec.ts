import { test, expect } from './fixtures'
const movie = {
  id: 329865,
  title: 'Arrival',
  year: 2016,
  runtime_minutes: 116,
  language: 'English',
  genres: ['Drama'],
  director: 'Denis Villeneuve',
  cast: [],
  overview: 'A linguist communicates with visitors.',
  tagline: '',
  cover_url: null,
  source: 'demo',
  artwork_kind: 'placeholder',
}
const response = {
  items: [movie],
  total: 1,
  indexed_movies: 10,
  data_source: 'demo',
  limited: true,
  page: 1,
  page_size: 20,
  total_pages: 1,
  match_type: 'keyword',
}

test('typing coalesces requests without submitting', async ({ page }) => {
  const queries: string[] = []
  await page.route('**/api/search/catalog*', (route) => {
    queries.push(new URL(route.request().url()).searchParams.get('q') ?? '')
    return route.fulfill({ json: response })
  })
  await page.goto('/')
  await expect(
    page.getByRole('link', { name: 'Explore Arrival', exact: true }),
  ).toBeVisible()
  queries.length = 0
  await page.clock.install()
  await page.clock.pauseAt(new Date(Date.now() + 1000))
  const input = page.getByRole('searchbox')
  await input.fill('Ar')
  await page.clock.runFor(100)
  await input.fill('Arri')
  await page.clock.runFor(100)
  await input.fill('Arrival')
  await page.clock.runFor(349)
  expect(queries).toEqual([])
  await page.clock.runFor(1)
  await expect(page).toHaveURL(/q=Arrival/)
  await expect.poll(() => queries).toEqual(['Arrival'])
  await page.clock.resume()
  await expect(page.locator('.results-line [role=status]')).toContainText(
    'matching “Arrival”',
  )
  expect(queries).toEqual(['Arrival'])
  await expect(
    page.getByText('Explore more films and filmographies', { exact: true }),
  ).toHaveCount(0)
})

test('automatic search resets pages, preserves filters and supports clearing', async ({
  page,
}) => {
  const requests: URL[] = []
  await page.route('**/api/search/catalog*', (route) => {
    requests.push(new URL(route.request().url()))
    return route.fulfill({ json: response })
  })
  await page.goto(
    '/?q=old&page=3&genre=Drama&language=English&max_runtime=120&lookup=names&person_id=20&name_page=2',
  )
  await page.getByRole('searchbox').fill('Arrival')
  await expect(page).toHaveURL(/q=Arrival/)
  await expect
    .poll(() => requests.at(-1)?.searchParams.get('q'))
    .toBe('Arrival')
  const latest = requests.at(-1)!.searchParams
  expect(latest.get('page')).toBe('1')
  expect(latest.get('genre')).toBe('Drama')
  expect(latest.get('language')).toBe('English')
  expect(latest.get('max_runtime')).toBe('120')
  for (const key of ['page', 'lookup', 'person_id', 'name_page'])
    expect(new URL(page.url()).searchParams.has(key)).toBe(false)
  await page.getByRole('searchbox').fill('')
  await expect.poll(() => new URL(page.url()).searchParams.get('q')).toBe(null)
  await expect(page.getByLabel('Genre', { exact: true })).toHaveValue('Drama')
})

test('late results cannot replace latest query; Enter works immediately', async ({
  page,
}) => {
  let releaseOld!: () => void
  const old = new Promise<void>((resolve) => {
    releaseOld = resolve
  })
  await page.route('**/api/search/catalog*', async (route) => {
    const q = new URL(route.request().url()).searchParams.get('q')
    if (q === 'old') await old
    await route
      .fulfill({
        json: {
          ...response,
          items: [
            { ...movie, title: q === 'old' ? 'Old result' : 'Latest result' },
          ],
        },
      })
      .catch(() => {})
  })
  await page.goto('/?q=old', { waitUntil: 'domcontentloaded' })
  await page.getByRole('searchbox').fill('new')
  await page.getByRole('searchbox').press('Enter')
  await expect(page).toHaveURL(/q=new/)
  await expect(
    page.getByRole('heading', { name: 'Latest result', exact: true }),
  ).toBeVisible()
  releaseOld()
  await expect(
    page.getByRole('heading', { name: 'Old result', exact: true }),
  ).toHaveCount(0)
  await expect(page.getByRole('searchbox')).toHaveValue('new')
})

test('unfinished composed text is not searched', async ({ page }) => {
  const queries: string[] = []
  await page.route('**/api/search/catalog*', (route) => {
    queries.push(new URL(route.request().url()).searchParams.get('q') ?? '')
    return route.fulfill({ json: response })
  })
  await page.goto('/')
  await expect(
    page.getByRole('heading', { name: 'Arrival', exact: true }),
  ).toBeVisible()
  queries.length = 0
  await page.clock.install()
  await page.clock.pauseAt(new Date(Date.now() + 1000))
  const input = page.getByRole('searchbox')
  await input.dispatchEvent('compositionstart')
  await input.fill('千と千尋')
  await page.clock.runFor(500)
  expect(queries).toEqual([])
  await input.dispatchEvent('compositionend')
  await page.clock.runFor(350)
  await expect.poll(() => queries).toEqual(['千と千尋'])
})

test('a pause after a space preserves the next word of a title', async ({
  page,
}) => {
  await page.route('**/api/search/catalog*', (route) =>
    route.fulfill({ json: response }),
  )
  await page.goto('/')
  const input = page.getByRole('searchbox')
  await input.fill('Knives ')
  await expect
    .poll(() => new URL(page.url()).searchParams.get('q'))
    .toBe('Knives')
  await expect(input).toHaveValue('Knives ')
  await input.pressSequentially('Out')
  await expect
    .poll(() => new URL(page.url()).searchParams.get('q'))
    .toBe('Knives Out')
  await expect(input).toHaveValue('Knives Out')
})
