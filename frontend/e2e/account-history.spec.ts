import { test, expect, signInMember } from './fixtures'
import type { Page } from '@playwright/test'
const origin = 'http://127.0.0.1:5176'
async function history(page: Page, kind = 'movies') {
  return await (await page.request.get(`/api/me/history/${kind}`)).json()
}
async function authHeaders(page: Page) {
  const response = await page.request.get('/api/auth/session')
  const session = await response.json()
  return {
    Origin: new URL(response.url()).origin,
    'X-CSRF-Token': session.csrf_token,
    'X-Account-Owner': session.user.id,
  }
}
async function complete(page: Page) {
  const options = page.locator('.quiz-options')
  await expect(options.first()).toBeVisible()
  for (const group of await options.all())
    await group.getByRole('button').first().click()
  await expect(
    page.getByText('Round saved to quiz history', { exact: true }),
  ).toBeVisible()
}

test('successful page visits persist; sections do not duplicate and recording can be paused', async ({
  page,
}) => {
  await signInMember(page, origin)
  await page.goto('/movies/157336')
  await expect.poll(async () => (await history(page)).total).toBe(1)
  await page.getByRole('link', { name: 'About', exact: true }).click()
  await page.getByRole('link', { name: 'Quiz', exact: true }).click()
  expect((await history(page)).total).toBe(1)
  await page.goto('/movies/27205')
  await expect.poll(async () => (await history(page)).total).toBe(2)
  await page.goto('/account')
  const panel = page.locator('.account-history')
  await expect(panel.getByRole('link', { name: /Inception/ })).toBeVisible()
  await expect(panel.getByRole('link', { name: /Interstellar/ })).toBeVisible()
  await page.getByRole('switch', { name: 'Save movie-page history' }).uncheck()
  await page.getByRole('button', { name: 'Save preferences' }).click()
  await expect(page.locator('.preferences-notice').first()).toContainText(
    'Preferences saved',
  )
  await page.goto('/movies/329865')
  await expect(
    page.getByRole('heading', { name: 'Arrival', exact: true }),
  ).toBeVisible()
  expect((await history(page)).total).toBe(2)
  await page.goto('/account')
  await expect(
    panel.getByText(
      'Movie-page history is paused. Existing visits remain here.',
    ),
  ).toBeVisible()
  await page.reload()
  await expect(
    page.getByRole('switch', { name: 'Save movie-page history' }),
  ).not.toBeChecked()
})

test('completed rounds are saved with server scores; replay creates a new round', async ({
  page,
}) => {
  await signInMember(page, origin)
  await page.goto('/movies/157336#quiz')
  await page
    .getByRole('switch', { name: 'Allow spoilers', exact: true })
    .check()
  await complete(page)
  const first = await history(page, 'quizzes')
  expect(first.total).toBe(1)
  expect(first.items[0].scored_questions).toBeGreaterThanOrEqual(10)
  expect(first.items[0].score).toBeLessThanOrEqual(
    first.items[0].scored_questions,
  )
  await page.getByRole('button', { name: 'Play again', exact: true }).click()
  await complete(page)
  const second = await history(page, 'quizzes')
  expect(second.total).toBe(2)
  expect(second.items[0].id).not.toBe(first.items[0].id)
  await page.goto('/account')
  await page.getByRole('button', { name: 'Quiz history', exact: true }).click()
  await expect(page.locator('.history-score')).toHaveCount(2)
  await page.reload()
  await page.getByRole('button', { name: 'Quiz history', exact: true }).click()
  await expect(page.locator('.history-score')).toHaveCount(2)
})

test('failed round save retains answers and retry uses the same round ID', async ({
  page,
}) => {
  await signInMember(page, origin)
  let fail = true
  const ids: string[] = []
  await page.route('**/api/me/history/quizzes', (route) => {
    if (route.request().method() !== 'POST') return route.continue()
    ids.push(route.request().postDataJSON().event_id)
    return fail
      ? route.fulfill({
          status: 503,
          json: { detail: 'Round history is temporarily unavailable.' },
        })
      : route.continue()
  })
  await page.goto('/movies/157336#quiz')
  await page
    .getByRole('switch', { name: 'Allow spoilers', exact: true })
    .check()
  await expect(page.locator('.quiz-options').first()).toBeVisible()
  for (const group of await page.locator('.quiz-options').all())
    await group.getByRole('button').first().click()
  await expect(
    page.getByText('Round history is temporarily unavailable.', {
      exact: true,
    }),
  ).toBeVisible()
  await expect(page.locator('.quiz-score')).toContainText('ROUND COMPLETE')
  fail = false
  await page
    .getByRole('button', { name: 'Retry saving round', exact: true })
    .click()
  await expect(
    page.getByText('Round saved to quiz history', { exact: true }),
  ).toBeVisible()
  expect(new Set(ids).size).toBe(1)
  expect((await history(page, 'quizzes')).total).toBe(1)
})

test('history paginates, clear requires confirmation and clears only the selected history', async ({
  page,
}) => {
  await signInMember(page, origin)
  const headers = await authHeaders(page)
  for (let i = 0; i < 11; i++)
    expect(
      (
        await page.request.post('/api/me/history/movies', {
          headers,
          data: {
            movie_id: i % 2 ? 27205 : 157336,
            event_id: crypto.randomUUID(),
          },
        })
      ).ok(),
    ).toBe(true)
  await page.goto('/account')
  const panel = page.locator('.account-history')
  await expect(panel.locator('.history-list li')).toHaveCount(10)
  await panel.getByRole('button', { name: 'Next', exact: true }).click()
  await expect(panel.locator('.history-list li')).toHaveCount(1)
  await panel
    .getByRole('button', { name: 'Clear history', exact: true })
    .click()
  await panel.getByRole('button', { name: 'Cancel', exact: true }).click()
  expect((await history(page)).total).toBe(11)
  await panel
    .getByRole('button', { name: 'Clear history', exact: true })
    .click()
  await panel
    .getByRole('button', { name: 'Confirm clear', exact: true })
    .click()
  await expect(
    panel.getByText('Movie-page history cleared', { exact: true }),
  ).toBeVisible()
  expect((await history(page)).total).toBe(0)
  await panel.getByRole('button', { name: 'Quiz history', exact: true }).click()
  await expect(
    panel.getByText('Finish a quiz to save your first round.'),
  ).toBeVisible()
})

test('guests do not record movie visits', async ({ page }) => {
  let writes = 0
  await page.route('**/api/me/history/movies', (route) => {
    if (route.request().method() === 'POST') writes++
    return route.continue()
  })
  await page.goto('/movies/157336')
  await expect(
    page.getByRole('heading', { name: 'Interstellar', exact: true }),
  ).toBeVisible()
  await page.getByRole('link', { name: 'About', exact: true }).click()
  expect(writes).toBe(0)
  expect((await page.request.get('/api/me/history/movies')).status()).toBe(401)
})

for (const width of [1440, 768, 375])
  test(`history rows and preferences fit at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 })
    await signInMember(page, origin)
    const headers = await authHeaders(page)
    await page.request.post('/api/me/history/movies', {
      headers,
      data: { movie_id: 157336, event_id: crypto.randomUUID() },
    })
    await page.goto('/account')
    await expect(page.locator('.history-film').first()).toBeVisible()
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true)
    await page
      .getByRole('button', { name: 'Quiz history', exact: true })
      .focus()
    expect(
      await page
        .getByRole('button', { name: 'Quiz history', exact: true })
        .evaluate((el) => getComputedStyle(el).outlineStyle),
    ).toBe('solid')
    if (width === 1440) {
      await page
        .getByRole('button', { name: 'Recently viewed', exact: true })
        .click()
      await page.screenshot({
        path: '/Users/gmadkaik/Documents/ai-projects/movie-companion/.cache/previews/plotspot-account-history.png',
        fullPage: true,
      })
    }
  })
