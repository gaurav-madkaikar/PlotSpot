import { test, expect } from './fixtures'

const movie = {
  id: 91001,
  title: 'New Discovery',
  adult: true,
  year: 2020,
  runtime_minutes: 100,
  language: 'English',
  genres: ['Drama'],
  director: 'Alex Lee',
  cast: [],
  overview: 'A new film.',
  tagline: '',
  cover_url: null,
  source: 'tmdb',
  artwork_kind: 'placeholder',
}
const person = {
  id: 20,
  name: 'Alex Lee',
  known_for_department: 'Directing',
  known_for_titles: ['New Discovery'],
}
const token = 'a'.repeat(32)
const response = {
  items: [movie],
  total: 1,
  data_source: 'tmdb',
  page: 1,
  page_size: 20,
  total_pages: 1,
  search_token: token,
  people: [],
  partial: false,
}

test('local and discovered movies share one grid without a lookup panel', async ({
  page,
}) => {
  let externalCalls = 0
  await page.route('**/api/search/names*', (route) => {
    externalCalls++
    return route.fulfill({ json: {} })
  })
  await page.route('**/api/search/catalog*', (route) =>
    route.fulfill({
      json: {
        ...response,
        items: [movie, { ...movie, id: 91002, title: 'Saved Discovery' }],
      },
    }),
  )
  await page.goto('/?q=Discovery&lookup=names')
  await expect(
    page.getByRole('link', { name: 'Explore New Discovery', exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('link', { name: 'Explore Saved Discovery', exact: true }),
  ).toBeVisible()
  await expect(page.locator('.movie-grid')).toHaveCount(1)
  await expect(
    page.getByText('More title and person matches', { exact: true }),
  ).toHaveCount(0)
  await expect(
    page.getByRole('region', { name: 'Title and person results' }),
  ).toHaveCount(0)
  expect(externalCalls).toBe(0)
})

test('unified suggestions preserve person identity, filters and stable pages', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 })
  const requests: URL[] = []
  await page.route('**/api/search/catalog*', (route) => {
    const url = new URL(route.request().url())
    requests.push(url)
    const selected = url.searchParams.has('person_id')
    const number = Number(url.searchParams.get('page') ?? 1)
    return route.fulfill({
      json: {
        ...response,
        people: selected
          ? []
          : [
              person,
              {
                ...person,
                id: 21,
                known_for_department: 'Acting',
                known_for_titles: ['Another Film'],
              },
            ],
        selected_person: selected ? person : null,
        person_role: selected ? url.searchParams.get('role') : null,
        page: number,
        total: selected ? 21 : 1,
        total_pages: selected ? 2 : 1,
      },
    })
  })
  await page.route('**/api/movies/91001', (route) =>
    route.fulfill({ json: movie }),
  )
  await page.goto('/?q=Alex+Lee&genre=Drama&language=English')
  const choices = page.getByRole('region', { name: 'Search suggestions' })
  await expect(
    choices.getByRole('button', { name: /^Search for / }),
  ).toHaveCount(2)
  await choices.getByRole('button').filter({ hasText: 'New Discovery' }).click()
  await expect(page.getByRole('group', { name: 'Movie credits' })).toHaveCount(
    0,
  )
  await expect(
    page.getByText('Which person did you mean?', { exact: true }),
  ).toHaveCount(0)
  await expect(page).toHaveURL(/person_id=20/)
  await page
    .getByRole('navigation', { name: 'Movie pages' })
    .getByRole('button', { name: 'Next', exact: true })
    .click()
  await expect(page.getByText('Page 2 of 2', { exact: true })).toBeVisible()
  expect(requests.at(-1)?.searchParams.get('genre')).toBe('Drama')
  expect(requests.at(-1)?.searchParams.get('language')).toBe('English')
  expect(requests.at(-1)?.searchParams.get('search_token')).toBe(token)
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true)
  await page.getByRole('link', { name: 'Explore New Discovery' }).click()
  await expect(
    page.getByRole('heading', { name: 'New Discovery', level: 1 }),
  ).toBeVisible()
  await page.goBack()
  await expect(page).toHaveURL(/page=2/)
  await expect(page.getByText('Page 2 of 2', { exact: true })).toBeVisible()
  await expect(
    page.getByRole('button', { name: 'Acting', exact: true }),
  ).toHaveCount(0)
  await expect(
    page.getByRole('button', { name: 'Directed', exact: true }),
  ).toHaveCount(0)
})

test('partial search with usable movies does not show a warning', async ({
  page,
}) => {
  await page.route('**/api/search/catalog*', (route) =>
    route.fulfill({ json: { ...response, partial: true } }),
  )
  await page.goto('/?q=Discovery')
  await expect(
    page.getByRole('link', { name: 'Explore New Discovery', exact: true }),
  ).toBeVisible()
  await expect(
    page.getByText('Some matches couldn’t be loaded.', { exact: false }),
  ).toHaveCount(0)
  await expect(
    page.getByRole('button', { name: 'Try again', exact: true }),
  ).toHaveCount(0)
})

test('failed search without movies offers retry rather than claiming no matches', async ({
  page,
}) => {
  let fails = true
  await page.route('**/api/search/catalog*', (route) =>
    route.fulfill({
      json: {
        ...response,
        partial: fails,
        items: fails ? [] : response.items,
        total: fails ? 0 : 1,
      },
    }),
  )
  await page.goto('/?q=Discovery')
  await expect(
    page.getByRole('heading', { name: 'Search couldn’t be completed.' }),
  ).toBeVisible()
  await expect(
    page.getByText('No films found just yet.', { exact: true }),
  ).toHaveCount(0)
  fails = false
  await page.getByRole('button', { name: 'Try again', exact: true }).click()
  await expect(
    page.getByRole('link', { name: 'Explore New Discovery', exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: 'Try again', exact: true }),
  ).toHaveCount(0)
})

test('expired snapshot resets the URL to the first page without losing filters', async ({
  page,
}) => {
  const nextToken = 'b'.repeat(32)
  await page.route('**/api/search/catalog*', (route) => {
    const current = new URL(route.request().url()).searchParams.get(
      'search_token',
    )
    return route.fulfill({
      json: {
        ...response,
        search_token: nextToken,
        snapshot_reset: current === token,
      },
    })
  })
  await page.goto(`/?q=Discovery&page=2&genre=Drama&search_token=${token}`)
  await expect(
    page.getByRole('link', { name: 'Explore New Discovery', exact: true }),
  ).toBeVisible()
  await expect
    .poll(() => new URL(page.url()).searchParams.get('page'))
    .toBe(null)
  expect(new URL(page.url()).searchParams.get('genre')).toBe('Drama')
  expect(new URL(page.url()).searchParams.get('search_token')).toBe(nextToken)
})

test('Batman results do not introduce unrelated people or role controls', async ({
  page,
}) => {
  await page.route('**/api/search/suggestions*', (route) =>
    route.fulfill({ json: { items: [], indexed_movies: 1500, limited: true } }),
  )
  await page.route('**/api/search/catalog*', (route) =>
    route.fulfill({
      json: {
        ...response,
        items: [{ ...movie, title: 'Batman' }],
        people: [
          {
            id: 1,
            name: 'Batman',
            known_for_department: 'Acting',
            known_for_titles: ['Other Film'],
          },
          {
            id: 2,
            name: 'Batman Jones',
            known_for_department: 'Acting',
            known_for_titles: ['Other Film'],
          },
        ],
      },
    }),
  )
  await page.goto('/?q=batman')
  await expect(
    page.getByRole('link', { name: 'Explore Batman', exact: true }),
  ).toBeVisible()
  await expect(
    page.getByText('Which person did you mean?', { exact: true }),
  ).toHaveCount(0)
  await expect(
    page.getByRole('region', { name: 'Search suggestions' }),
  ).toHaveCount(0)
  await expect(page.getByRole('group', { name: 'Movie credits' })).toHaveCount(
    0,
  )
})

test('sydney sweene merges actor identities and movie suggestions in one block', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 })
  const requests: URL[] = []
  const people = [
    {
      id: 115440,
      name: 'Sydney Sweeney',
      known_for_department: 'Acting',
      known_for_titles: ['Anyone but You'],
    },
    {
      id: 2131671,
      name: 'Sydney Sweeney',
      known_for_department: 'Acting',
      known_for_titles: ['Yield'],
    },
  ]
  await page.route('**/api/search/suggestions*', (route) =>
    route.fulfill({
      json: {
        items: [
          {
            label: 'Sydney Sweeney',
            kind: 'actor',
            movie_ids: [91001],
            score: 0.96,
          },
          { label: 'Sydney', kind: 'movie', movie_ids: [91002], score: 0.8 },
          {
            label: 'Sydney Swan',
            kind: 'director',
            movie_ids: [91003],
            score: 0.8,
          },
        ],
        indexed_movies: 1500,
        limited: true,
      },
    }),
  )
  await page.route('**/api/search/catalog*', (route) => {
    const url = new URL(route.request().url())
    requests.push(url)
    const selected = url.searchParams.has('person_id')
    return route.fulfill({
      json: {
        ...response,
        people: selected ? [] : people,
        items: [{ ...movie, title: 'Anyone but You' }],
        selected_person: selected ? people[0] : null,
        person_role: selected ? 'actor' : null,
      },
    })
  })
  await page.goto(
    '/?q=sydney+sweene&genre=Drama&language=English&max_runtime=120',
  )
  const options = page.getByRole('region', { name: 'Search suggestions' })
  await expect(options).toHaveCount(1)
  await expect(
    options.getByRole('button', { name: /^Search for / }),
  ).toHaveCount(4)
  await expect(
    options.getByRole('button', {
      name: 'Search for Sydney Sweeney (actor)',
      exact: true,
    }),
  ).toHaveCount(0)
  await expect(
    options.getByRole('button', {
      name: 'Search for Sydney (movie)',
      exact: true,
    }),
  ).toBeVisible()
  await expect(
    options.getByRole('button', {
      name: 'Search for Sydney Swan (director)',
      exact: true,
    }),
  ).toBeVisible()
  await options
    .getByRole('button', {
      name: 'Search for Sydney Sweeney (actor), known for Anyone but You',
      exact: true,
    })
    .click()
  await expect(page.getByRole('searchbox')).toHaveValue('Sydney Sweeney')
  await expect
    .poll(() => requests.at(-1)?.searchParams.get('person_id'))
    .toBe('115440')
  expect(requests.at(-1)?.searchParams.get('role')).toBe('actor')
  expect(requests.at(-1)?.searchParams.get('genre')).toBe('Drama')
  expect(requests.at(-1)?.searchParams.get('language')).toBe('English')
  expect(requests.at(-1)?.searchParams.get('max_runtime')).toBe('120')
  await expect(
    page.getByRole('link', { name: 'Explore Anyone but You', exact: true }),
  ).toBeVisible()
  await expect(
    page.getByText('Which person did you mean?', { exact: true }),
  ).toHaveCount(0)
  await expect(
    page.getByRole('button', { name: 'Acting', exact: true }),
  ).toHaveCount(0)
  await expect(
    page.getByRole('button', { name: 'Directed', exact: true }),
  ).toHaveCount(0)
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true)
})
