import { test, expect } from './fixtures'

const movie = {
  id: 157336,
  title: 'Interstellar',
  year: 2014,
  runtime_minutes: 169,
  language: 'English',
  genres: ['Science Fiction'],
  director: 'Christopher Nolan',
  cast: [],
  overview: 'An expedition through space.',
  tagline: '',
  cover_url: null,
  source: 'tmdb',
  artwork_kind: 'placeholder',
}
const response = {
  items: [movie],
  total: 1,
  data_source: 'tmdb',
  page: 1,
  page_size: 20,
  total_pages: 1,
  search_token: 'a'.repeat(32),
  partial: false,
}

test('saved matches render before live discovery and pagination waits for the frozen pool', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 })
  let release = () => {}
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route('**/api/search/local*', (route) =>
    route.fulfill({
      json: { ...response, total_pages: 0, search_token: null },
    }),
  )
  await page.route('**/api/search/catalog*', async (route) => {
    await gate
    await route.fulfill({
      json: {
        ...response,
        items: [
          movie,
          ...Array.from({ length: 19 }, (_, i) => ({
            ...movie,
            id: 91001 + i,
            title: `New Discovery ${i + 1}`,
          })),
        ],
        total: 21,
        total_pages: 2,
      },
    })
  })
  try {
    await page.goto('/?q=Interstell&genre=Science+Fiction&language=English')
    await expect(
      page.getByRole('link', { name: 'Explore Interstellar', exact: true }),
    ).toBeVisible()
    await expect(
      page.getByText('Finding more films…', { exact: true }),
    ).toBeVisible()
    await expect(
      page.getByRole('navigation', { name: 'Movie pages' }),
    ).toHaveCount(0)
    release()
    await expect(page.locator('.movie-card')).toHaveCount(20)
    await expect(
      page.getByText('Finding more films…', { exact: true }),
    ).toHaveCount(0)
    await expect(
      page.getByRole('navigation', { name: 'Movie pages' }),
    ).toBeVisible()
    await expect(page.getByLabel('Language', { exact: true })).toHaveValue(
      'English',
    )
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true)
  } finally {
    release()
  }
})

test('late live results cannot replace the next query or its saved results', async ({
  page,
}) => {
  let release = () => {}
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route('**/api/search/local*', (route) => {
    const q = new URL(route.request().url()).searchParams.get('q')
    return route.fulfill({
      json: {
        ...response,
        items:
          q === 'Arrival'
            ? [{ ...movie, id: 329865, title: 'Arrival' }]
            : [movie],
        total_pages: 0,
        search_token: null,
      },
    })
  })
  await page.route('**/api/search/catalog*', async (route) => {
    const q = new URL(route.request().url()).searchParams.get('q')
    if (q === 'Arrival') await gate
    await route.fulfill({
      json: {
        ...response,
        items:
          q === 'Arrival'
            ? [{ ...movie, id: 329865, title: 'Arrival' }]
            : [movie],
      },
    })
  })
  try {
    await page.goto('/?q=Arrival')
    await expect(
      page.getByRole('link', { name: 'Explore Arrival', exact: true }),
    ).toBeVisible()
    await page.getByRole('searchbox').fill('Interstell')
    await page.getByRole('searchbox').press('Enter')
    await expect(
      page.getByRole('link', { name: 'Explore Interstellar', exact: true }),
    ).toBeVisible()
    release()
    await expect(
      page.getByRole('link', { name: 'Explore Arrival', exact: true }),
    ).toHaveCount(0)
  } finally {
    release()
  }
})

test('live failure retains usable saved matches and offers retry', async ({
  page,
}) => {
  let failures = true
  await page.route('**/api/search/local*', (route) =>
    route.fulfill({
      json: { ...response, total_pages: 0, search_token: null },
    }),
  )
  await page.route('**/api/search/catalog*', (route) =>
    failures
      ? route.fulfill({ status: 503, json: { detail: 'Unavailable' } })
      : route.fulfill({ json: response }),
  )
  await page.goto('/?q=Interstell')
  await expect(
    page.getByRole('link', { name: 'Explore Interstellar', exact: true }),
  ).toBeVisible()
  const retry = page.getByRole('button', {
    name: 'Retry live search',
    exact: true,
  })
  await expect(retry).toBeVisible()
  failures = false
  await retry.click()
  await expect(retry).toHaveCount(0)
  await expect(page.locator('.movie-card')).toHaveCount(1)
})

test('empty saved preview waits for live discovery before claiming no matches', async ({
  page,
}) => {
  let release = () => {}
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route('**/api/search/local*', (route) =>
    route.fulfill({
      json: {
        ...response,
        items: [],
        total: 0,
        total_pages: 0,
        search_token: null,
      },
    }),
  )
  await page.route('**/api/search/catalog*', async (route) => {
    await gate
    await route.fulfill({ json: response })
  })
  try {
    await page.goto('/?q=Unknown+to+catalog')
    await expect(
      page.getByText('Finding your results…', { exact: true }),
    ).toBeVisible()
    await expect(
      page.getByRole('heading', { name: 'No films found just yet.' }),
    ).toHaveCount(0)
    release()
    await expect(
      page.getByRole('link', { name: 'Explore Interstellar', exact: true }),
    ).toBeVisible()
  } finally {
    release()
  }
})
