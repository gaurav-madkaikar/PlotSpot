import { test, expect } from './fixtures'

test('exact movie titles suppress even stale suggestion responses', async ({
  page,
}) => {
  await page.route('**/api/search/suggestions*', (route) =>
    route.fulfill({
      json: {
        items: [
          {
            label: 'Interstellar Wars',
            kind: 'movie',
            movie_ids: [123],
            score: 0.8,
          },
        ],
        indexed_movies: 1500,
        limited: true,
      },
    }),
  )
  await page.goto('/?q=Interstellar')
  await expect(
    page.getByRole('link', { name: 'Explore Interstellar', exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('region', { name: 'Search suggestions' }),
  ).toHaveCount(0)
})

test('title completion returns the film and suggestions can be dismissed per query', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/?q=Interstell')
  const panel = page.getByRole('region', { name: 'Search suggestions' })
  await expect(page.locator('.movie-card').first()).toContainText(
    'Interstellar',
  )
  await expect(
    page.getByRole('button', {
      name: 'Search for Interstellar (movie)',
      exact: true,
    }),
  ).toBeVisible()
  const close = page.getByRole('button', { name: 'Dismiss search suggestions' })
  const bounds = await close.boundingBox()
  expect(bounds?.width).toBeGreaterThanOrEqual(44)
  expect(bounds?.height).toBeGreaterThanOrEqual(44)
  await close.focus()
  await page.keyboard.press('Enter')
  await expect(panel).toHaveCount(0)
  await page.getByLabel('Language', { exact: true }).selectOption('English')
  await expect(
    page.getByRole('link', { name: 'Explore Interstellar', exact: true }),
  ).toBeVisible()
  await expect(panel).toHaveCount(0)
  await page.getByRole('searchbox').fill('Intersteler')
  await expect(panel).toBeVisible()
  await page
    .getByRole('button', {
      name: 'Search for Interstellar (movie)',
      exact: true,
    })
    .click()
  await expect(page.getByRole('searchbox')).toHaveValue('Interstellar')
  await expect(panel).toHaveCount(0)
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true)
})

test('movie typo suggestion preserves hard filters and clears cleanly', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto(
    '/?q=Intersteler&genre=Science+Fiction&max_runtime=120&language=English',
  )
  await page
    .getByRole('button', {
      name: 'Search for Interstellar (movie)',
      exact: true,
    })
    .click()
  await expect(page.getByRole('searchbox')).toHaveValue('Interstellar')
  await expect(page.getByLabel('Maximum runtime')).toHaveValue('120')
  await expect(page.getByLabel('Language', { exact: true })).toHaveValue(
    'English',
  )
  await expect(
    page.getByRole('heading', { name: 'No films found just yet.' }),
  ).toBeVisible()
  await expect(
    page.getByRole('region', { name: 'Search suggestions' }),
  ).toHaveCount(0)
  await page.getByLabel('Maximum runtime').selectOption('')
  await expect(
    page.getByRole('link', { name: 'Explore Interstellar', exact: true }),
  ).toBeVisible()
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true)
  await page.getByRole('button', { name: 'Clear filters', exact: true }).click()
  await expect(page.locator('.movie-card')).toHaveCount(10)
  await expect(
    page.getByRole('region', { name: 'Search suggestions' }),
  ).toHaveCount(0)
})

test('actor typo suggestion retrieves the actor film', async ({ page }) => {
  await page.goto('/?q=Amy+Admas')
  await page
    .getByRole('button', { name: 'Search for Amy Adams (actor)', exact: true })
    .click()
  await expect(
    page.getByRole('link', { name: 'Explore Arrival', exact: true }),
  ).toBeVisible()
})

test('optional suggestion failure leaves normal search usable', async ({
  page,
}) => {
  await page.route('**/api/search/suggestions*', (route) =>
    route.fulfill({ status: 503, json: { detail: 'Unavailable' } }),
  )
  await page.goto('/?q=Arrival')
  await expect(
    page.getByRole('link', { name: 'Explore Arrival', exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('region', { name: 'Search suggestions' }),
  ).toHaveCount(0)
})

test('director typo suggestions and description keywords use the single icon search', async ({
  page,
}) => {
  await page.goto('/')
  const search = page.getByRole('searchbox')
  const submit = page.getByRole('button', { name: 'Search', exact: true })
  await expect(submit).toHaveText('')
  await expect(page.locator('.search-field > svg')).toHaveCount(0)
  await search.fill('Cristopher Nolan')
  await search.press('Enter')
  await expect(
    page.getByRole('link', { name: 'Explore Inception', exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('link', { name: 'Explore Interstellar', exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', {
      name: 'Search for Christopher Nolan (director)',
    }),
  ).toBeVisible()
  await search.fill('linguistt')
  await submit.click()
  await expect(
    page.getByRole('link', { name: 'Explore Arrival', exact: true }),
  ).toBeVisible()
  await expect(page.locator('.movie-card')).toHaveCount(1)
  await expect(
    page.getByText('Showing matches for', { exact: false }),
  ).toContainText('linguist')
  await search.fill('quirky charming hotel adventure')
  await search.press('Enter')
  await expect(page.locator('.movie-card')).toHaveCount(0)
  await expect(
    page.getByRole('heading', { name: 'No films found just yet.' }),
  ).toBeVisible()
})
