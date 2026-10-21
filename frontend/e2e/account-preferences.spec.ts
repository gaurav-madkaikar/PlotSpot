import { test, expect, signInMember } from './fixtures'

async function openAccount(page: import('@playwright/test').Page) {
  await signInMember(page, 'http://127.0.0.1:5176')
  await page.goto('/account')
  await expect(
    page.getByRole('heading', { name: 'Viewing preferences' }),
  ).toBeVisible()
}

async function preferences(page: import('@playwright/test').Page) {
  return (await (await page.request.get('/api/auth/session')).json()).user
    .preferences
}

test('preferences save, reload, reset, spoiler override and account isolation', async ({
  page,
  browser,
}) => {
  await openAccount(page)
  const spoiler = page.getByRole('switch', {
    name: 'Allow spoilers by default',
  })
  const adult = page.getByRole('switch', {
    name: 'Include adult films in discovery',
  })
  await expect(spoiler).not.toBeChecked()
  await expect(adult).toBeChecked()
  await spoiler.check()
  await adult.uncheck()
  expect(await preferences(page)).toMatchObject({
    allow_spoilers: false,
    include_adult: true,
  })
  await page.getByRole('button', { name: 'Save preferences' }).click()
  await expect(page.locator('.preferences-notice')).toContainText(
    'Preferences saved',
  )
  await page.reload()
  await expect(spoiler).toBeChecked()
  await expect(adult).not.toBeChecked()
  await page.goto('/movies/157336')
  await expect(
    page.getByRole('switch', { name: 'Allow spoilers', exact: true }),
  ).toBeChecked()
  await page
    .getByRole('switch', { name: 'Allow spoilers', exact: true })
    .uncheck()
  await expect(
    page.getByRole('switch', { name: 'Allow spoilers', exact: true }),
  ).not.toBeChecked()
  await page.goto('/account')
  await page.getByRole('button', { name: 'Reset to defaults' }).click()
  expect(await preferences(page)).toMatchObject({
    allow_spoilers: true,
    include_adult: false,
  })
  await page.getByRole('button', { name: 'Save preferences' }).click()
  await expect(page.locator('.preferences-notice')).toContainText(
    'Preferences saved',
  )
  expect(await preferences(page)).toMatchObject({
    allow_spoilers: false,
    include_adult: true,
    revision: 2,
  })
  const context = await browser.newContext()
  try {
    const other = await context.newPage()
    await openAccount(other)
    expect(await preferences(other)).toEqual({
      revision: 0,
      track_movie_history: true,
      allow_spoilers: false,
      include_adult: true,
    })
  } finally {
    await context.close()
  }
})

test('failed save keeps edits and stale writes require deliberate reload', async ({
  page,
}) => {
  await openAccount(page)
  let fail = true
  await page.route('**/api/me/preferences', (route) =>
    fail
      ? route.fulfill({
          status: 503,
          json: { detail: 'Preferences unavailable test fixture.' },
        })
      : route.continue(),
  )
  await page.getByRole('switch', { name: 'Allow spoilers by default' }).check()
  await page.getByRole('button', { name: 'Save preferences' }).click()
  await expect(
    page.locator('.account-preferences [role="alert"]'),
  ).toContainText('unavailable')
  await expect(
    page.getByRole('switch', { name: 'Allow spoilers by default' }),
  ).toBeChecked()
  fail = false
  const session = await (await page.request.get('/api/auth/session')).json()
  const response = await page.request.put('/api/me/preferences', {
    headers: {
      Origin: 'http://127.0.0.1:5176',
      'X-CSRF-Token': session.csrf_token,
    },
    data: { ...session.user.preferences, include_adult: false },
  })
  expect(response.ok()).toBe(true)
  await page.getByRole('button', { name: 'Save preferences' }).click()
  await expect(
    page.getByRole('button', { name: 'Load latest preferences' }),
  ).toBeVisible()
  await expect(
    page.getByRole('switch', { name: 'Allow spoilers by default' }),
  ).toBeChecked()
  await page.getByRole('button', { name: 'Load latest preferences' }).click()
  await expect(
    page.getByRole('switch', { name: 'Allow spoilers by default' }),
  ).not.toBeChecked()
  await expect(
    page.getByRole('switch', { name: 'Include adult films in discovery' }),
  ).not.toBeChecked()
  await page.getByRole('switch', { name: 'Allow spoilers by default' }).check()
  await page.getByRole('button', { name: 'Save preferences' }).click()
  await expect(page.locator('.preferences-notice')).toContainText(
    'Preferences saved',
  )
})

test('discovery requests and cached results respect changed preference', async ({
  page,
}) => {
  await openAccount(page)
  const requested: string[] = []
  await page.route('**/api/search/catalog*', (route) => {
    const mode =
      new URL(route.request().url()).searchParams.get('include_adult') ?? 'true'
    requested.push(mode)
    return route.fulfill({
      json: {
        items: [],
        total: 0,
        page: 1,
        page_size: 20,
        total_pages: 0,
        data_source: 'demo',
      },
    })
  })
  await page.goto('/')
  await expect.poll(() => requested.at(-1)).toBe('true')
  await page.goto('/account')
  await page
    .getByRole('switch', { name: 'Include adult films in discovery' })
    .uncheck()
  await page.getByRole('button', { name: 'Save preferences' }).click()
  await expect(page.locator('.preferences-notice')).toContainText(
    'Preferences saved',
  )
  await page.goto('/')
  await expect.poll(() => requested.at(-1)).toBe('false')
})

for (const width of [1440, 768, 375])
  test(`preferences align and fit at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 950 })
    await openAccount(page)
    const heading = await page.locator('.account-heading').boundingBox()
    const library = await page
      .locator('.account-layout > .account-card')
      .first()
      .boundingBox()
    expect(Math.abs(heading!.x - library!.x)).toBeLessThan(2)
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true)
    await page
      .getByRole('switch', { name: 'Allow spoilers by default' })
      .focus()
    const focus = await page
      .locator('#preference-allow_spoilers + .spoiler-track')
      .evaluate((el) => getComputedStyle(el).outlineStyle)
    expect(focus).toBe('solid')
    if (width === 1440)
      await page.screenshot({
        path: '../.cache/previews/plotspot-account-preferences.png',
        fullPage: true,
      })
  })
