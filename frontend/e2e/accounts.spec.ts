import { test, expect } from './fixtures'
import type { Page } from '@playwright/test'
const password = 'A test-only long passphrase!'
const username = () => `viewer_${crypto.randomUUID().slice(0, 12)}`
async function finishVerification(page: Page, name: string) {
  await expect(
    page.getByText('LOCAL EMAIL PREVIEW', { exact: true }),
  ).toBeVisible()
  await page
    .getByRole('link', { name: 'Open verification link', exact: true })
    .click()
  await expect(page).not.toHaveURL(/#verify=/)
  await page.getByRole('button', { name: 'Verify email', exact: true }).click()
  await expect(
    page.getByText('Email verified. You can sign in now.'),
  ).toBeVisible()
  await page.getByLabel('Username', { exact: true }).fill(name)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page
    .locator('form')
    .getByRole('button', { name: 'Sign in', exact: true })
    .click()
}
async function signup(page: Page, name: string) {
  if (page.url() === 'about:blank') await page.goto('/account')
  else
    await page
      .getByRole('navigation', { name: 'Main navigation' })
      .getByRole('link', { name: 'Sign in', exact: true })
      .click()
  await page
    .getByRole('button', { name: 'Create account', exact: true })
    .first()
    .click()
  await page.getByLabel('Username', { exact: true }).fill(name)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page
    .getByLabel('Email address', { exact: true })
    .fill(`${name}@example.com`)
  await page
    .getByRole('button', { name: 'Create account', exact: true })
    .last()
    .click()
  await finishVerification(page, name)
  await expect(
    page.getByText(`Signed in as ${name}.`, { exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('link', { name: 'Open collections' }),
  ).toBeVisible()
}
async function snapshot(page: Page) {
  const response = await page.request.get('/api/me/collection')
  expect(response.ok()).toBe(true)
  return (await response.json()).snapshot
}
async function csrf(page: Page) {
  return (await (await page.request.get('/api/auth/session')).json()).csrf_token
}
async function create(page: Page, name: string) {
  await page
    .getByRole('button', { name: 'New collection', exact: true })
    .click()
  await page.getByLabel('New collection name').fill(name)
  await page.getByRole('button', { name: 'Create', exact: true }).click()
}

test('browser saves stay separate until explicit import, and account data survives reload', async ({
  page,
}) => {
  await page.goto('/movies/157336')
  await page
    .getByRole('button', {
      name: 'Save Interstellar to collection',
      exact: true,
    })
    .click()
  await page.getByLabel('New collection name').fill('Weekend films')
  await page.getByRole('button', { name: 'Create', exact: true }).click()
  await page.getByRole('button', { name: 'Done', exact: true }).click()
  const name = username()
  await signup(page, name)
  await page
    .getByRole('link', { name: 'Open collections', exact: true })
    .click()
  await expect(page).toHaveURL(/\/collections$/)
  const button = page.getByRole('button', { name: 'Keep these saves' })
  await expect(button).toBeEnabled()
  expect((await snapshot(page)).saved).toEqual([])
  await button.click()
  await expect(
    page.getByText('Saves added to your account', { exact: true }),
  ).toBeVisible()
  let saved = await snapshot(page)
  expect(saved.saved).toEqual([157336])
  expect(saved.collections[0].name).toBe('Weekend films')
  expect(
    await page.evaluate(() => localStorage.getItem('frame.demo.collection.v1')),
  ).toBeNull()
  await page.goto('/collections')
  await expect(page.getByRole('link', { name: /Weekend films/ })).toBeVisible()
  await create(page, 'Nolan night')
  await expect(
    page.getByRole('heading', { name: 'Nolan night', exact: true }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Rename', exact: true }).click()
  await page
    .getByLabel('Collection name', { exact: true })
    .fill('Next screening')
  await page.getByRole('button', { name: 'Save name', exact: true }).click()
  await expect(
    page.getByRole('heading', { name: 'Next screening', exact: true }),
  ).toBeVisible()
  await page.goto('/movies/157336')
  await page
    .getByRole('button', {
      name: 'Manage collections for Interstellar',
      exact: true,
    })
    .click()
  await page.getByRole('checkbox', { name: /Next screening/ }).check()
  await page.getByRole('button', { name: 'Done', exact: true }).click()
  await page.getByRole('switch', { name: 'Allow spoilers' }).check()
  await page.reload()
  await expect(
    page.getByRole('switch', { name: 'Allow spoilers' }),
  ).toBeChecked()
  saved = await snapshot(page)
  expect(
    saved.collections.find((c: any) => c.name === 'Next screening').movieIds,
  ).toEqual([157336])
  await page.goto('/account')
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
  await signup(page, username())
  expect((await snapshot(page)).saved).toEqual([])
  await page.goto('/collections')
  await expect(
    page.getByRole('link', { name: /Weekend films|Next screening/ }),
  ).toHaveCount(0)
  await page.goto('/account')
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await page.goto('/collections')
  await expect(page.getByRole('link', { name: /Weekend films/ })).toHaveCount(0)
})

test('two browser contexts have isolated account collections', async ({
  page,
  browser,
}) => {
  await signup(page, username())
  await page.goto('/movies/157336')
  await page
    .getByRole('button', {
      name: 'Save Interstellar to collection',
      exact: true,
    })
    .click()
  await page.getByRole('button', { name: 'Done', exact: true }).click()
  const context = await browser.newContext()
  const other = await context.newPage()
  try {
    await signup(other, username())
    expect((await snapshot(other)).saved).toEqual([])
    expect((await snapshot(page)).saved).toEqual([157336])
    await page.reload()
    expect((await snapshot(page)).saved).toEqual([157336])
  } finally {
    await context.close()
  }
})

test('stale writes retain the newer collection and can be retried', async ({
  page,
}) => {
  await signup(page, username())
  await page.goto('/collections')
  await expect(
    page.getByRole('button', { name: 'New collection', exact: true }),
  ).toBeEnabled()
  const current = await snapshot(page)
  const changed = {
    ...current,
    collections: [
      { id: crypto.randomUUID(), name: 'Another tab', movieIds: [] },
    ],
  }
  expect(
    (
      await page.request.put('/api/me/collection', {
        headers: {
          Origin: new URL(page.url()).origin,
          'X-CSRF-Token': await csrf(page),
        },
        data: changed,
      })
    ).ok(),
  ).toBe(true)
  await create(page, 'My next films')
  await expect(
    page.getByText(
      'The collection could not be created. Review the message and try again.',
      { exact: true },
    ),
  ).toBeVisible()
  expect((await snapshot(page)).collections.map((c: any) => c.name)).toEqual([
    'Another tab',
  ])
  await page.getByRole('button', { name: 'Create', exact: true }).click()
  await expect(
    page.getByRole('heading', { name: 'My next films', exact: true }),
  ).toBeVisible()
  expect((await snapshot(page)).collections.map((c: any) => c.name)).toEqual([
    'Another tab',
    'My next films',
  ])
})

test('expired CSRF is refreshed without automatically retrying credentials', async ({
  page,
}) => {
  let csrfRejected = false
  let attempts = 0
  await page.route('**/api/auth/register', async (route) => {
    attempts++
    if (!csrfRejected) {
      csrfRejected = true
      await route.fulfill({
        status: 403,
        json: {
          detail:
            'This request could not be verified. Refresh the page and try again.',
        },
      })
    } else await route.continue()
  })
  await page.goto('/account')
  await page
    .getByRole('button', { name: 'Create account', exact: true })
    .first()
    .click()
  const name = username()
  await page.getByLabel('Username', { exact: true }).fill(name)
  await page
    .getByLabel('Email address', { exact: true })
    .fill(`${name}@example.com`)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page
    .getByRole('button', { name: 'Create account', exact: true })
    .last()
    .click()
  await expect(page.getByRole('alert')).toContainText('could not be verified')
  expect(attempts).toBe(1)
  await page
    .getByRole('button', { name: 'Create account', exact: true })
    .last()
    .click()
  await finishVerification(page, name)
  await expect(
    page.getByRole('link', { name: 'Open collections' }),
  ).toBeVisible()
  expect(attempts).toBe(2)
})

test('failed private loads prevent edits and recover without guest fallback', async ({
  page,
}) => {
  await signup(page, username())
  let fail = true
  await page.route('**/api/me/collection', (route) =>
    fail
      ? route.fulfill({
          status: 503,
          json: { detail: 'Unavailable test fixture.' },
        })
      : route.continue(),
  )
  await page.reload()
  await expect(
    page.getByRole('button', { name: 'Retry collection' }),
  ).toBeVisible()
  expect(
    await page.evaluate(() => localStorage.getItem('frame.demo.collection.v1')),
  ).toBeNull()
  fail = false
  await page.getByRole('button', { name: 'Retry collection' }).click()
  await expect(
    page.getByRole('link', { name: 'Open collections' }),
  ).toBeVisible()
})

test('older delayed private read cannot overwrite a successful save', async ({
  page,
}) => {
  await signup(page, username())
  await page.goto('/collections')
  await expect(
    page.getByRole('button', { name: 'New collection', exact: true }),
  ).toBeEnabled()
  let release: () => void = () => {}
  let arrived: () => void = () => {}
  const held = new Promise<void>((resolve) => (release = resolve))
  const ready = new Promise<void>((resolve) => (arrived = resolve))
  let delay = true
  await page.route('**/api/me/collection', async (route) => {
    if (route.request().method() === 'GET' && delay) {
      delay = false
      const response = await route.fetch()
      arrived()
      await held
      await route.fulfill({ response })
    } else await route.continue()
  })
  // Focus revalidation starts a read under the same owner while a write finishes.
  const csrfToken = await csrf(page)
  let putArrived: () => void = () => {}
  let releasePut: () => void = () => {}
  const putReady = new Promise<void>((resolve) => (putArrived = resolve))
  const putHeld = new Promise<void>((resolve) => (releasePut = resolve))
  await page.route('**/api/me/collection', async (route) => {
    if (route.request().method() === 'PUT') {
      putArrived()
      await putHeld
      await route.continue()
    } else await route.fallback()
  })
  await page
    .getByRole('button', { name: 'New collection', exact: true })
    .click()
  await page.getByLabel('New collection name').fill('Freshly saved')
  await page.getByRole('button', { name: 'Create', exact: true }).click()
  await putReady
  await page.evaluate(() => window.dispatchEvent(new Event('focus')))
  await ready
  releasePut()
  await expect(page.locator('.sr-only[role="status"]')).toContainText(
    'Freshly saved created.',
  )
  release()
  await expect(
    page.getByRole('heading', { name: 'Freshly saved', exact: true }),
  ).toBeVisible()
  expect((await snapshot(page)).collections.map((c: any) => c.name)).toEqual([
    'Freshly saved',
  ])
  expect(csrfToken).toBeTruthy()
})

test('account form supports password managers, visibility and mobile width', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/account')
  await expect(
    page
      .getByRole('navigation', { name: 'Main navigation' })
      .getByRole('link', { name: 'Sign in', exact: true }),
  ).toBeVisible()
  const field = page.getByLabel('Password', { exact: true })
  await expect(field).toBeVisible()
  await expect(field).toHaveAttribute('autocomplete', 'current-password')
  await page.getByRole('button', { name: 'Show password', exact: true }).click()
  await expect(field).toHaveAttribute('type', 'text')
  await page.getByRole('button', { name: 'Hide password', exact: true }).click()
  await expect(field).toHaveAttribute('type', 'password')
  await page
    .getByRole('button', { name: 'Create account', exact: true })
    .first()
    .click()
  await expect(field).toHaveAttribute('autocomplete', 'new-password')
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true)
  await page.screenshot({
    path: '../.cache/proof/account-mobile.png',
    fullPage: true,
  })
})

test('persistent private authorization failure stops automatic recovery', async ({
  page,
}) => {
  await signup(page, username())
  let reads = 0
  await page.route('**/api/me/collection', (route) => {
    reads++
    return route.fulfill({
      status: 401,
      json: { detail: 'Rejected test fixture.' },
    })
  })
  await page.reload()
  await expect(
    page.getByRole('button', { name: 'Retry collection' }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: 'Retry collection' }),
  ).toBeVisible()
  // StrictMode can start one initial read that is cancelled; at most one
  // completed-read recovery follows. A persistent error stays on manual retry.
  expect(reads).toBeGreaterThanOrEqual(2)
  expect(reads).toBeLessThanOrEqual(3)
  expect(
    await page.evaluate(() => localStorage.getItem('frame.demo.collection.v1')),
  ).toBeNull()
})

test('PlotSpot navigation has a reel and a count-free Collections link', async ({
  page,
}) => {
  await page.goto('/')
  const nav = page.getByRole('navigation', { name: 'Main navigation' })
  await expect(
    page.getByRole('link', { name: 'PlotSpot home', exact: true }),
  ).toBeVisible()
  await expect(page.locator('.brand img')).toHaveAttribute(
    'src',
    '/plotspot-reel.svg',
  )
  await expect(
    nav.getByRole('link', { name: 'Collections', exact: true }),
  ).toHaveText('Collections')
  await expect(nav.locator('.nav-count')).toHaveCount(0)
  await expect(page).toHaveTitle('PlotSpot: Movie Companion')
})

test('registration rejects invalid email and login waits for verification', async ({
  page,
}) => {
  await page.goto('/account')
  await page
    .getByRole('button', { name: 'Create account', exact: true })
    .first()
    .click()
  const name = username()
  await page.getByLabel('Username', { exact: true }).fill(name)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByLabel('Email address', { exact: true }).fill('invalid-email')
  await page
    .getByRole('button', { name: 'Create account', exact: true })
    .last()
    .click()
  await expect(page.getByRole('alert')).toContainText('valid email address')
  await page
    .getByLabel('Email address', { exact: true })
    .fill(`${name}@example.com`)
  await page
    .getByRole('button', { name: 'Create account', exact: true })
    .last()
    .click()
  await expect(
    page.getByText('LOCAL EMAIL PREVIEW', { exact: true }),
  ).toBeVisible()
  expect((await page.request.get('/api/auth/session')).ok()).toBe(true)
  expect(
    (await (await page.request.get('/api/auth/session')).json()).user,
  ).toBeNull()
  await page
    .getByRole('button', { name: 'Back to sign in', exact: true })
    .click()
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page
    .locator('form')
    .getByRole('button', { name: 'Sign in', exact: true })
    .click()
  await expect(page.getByRole('alert')).toContainText(
    'Verify your email before signing in',
  )
  await expect(
    page.getByRole('button', { name: 'Resend verification link' }),
  ).toBeVisible()
  expect((await page.request.get('/api/me/collection')).status()).toBe(401)
})

test('email verification works while signed in without switching account ownership', async ({
  page,
}) => {
  const existing = username()
  await signup(page, existing)
  const pending = username()
  const response = await page.request.post('/api/auth/register', {
    headers: {
      Origin: new URL(page.url()).origin,
      'X-CSRF-Token': await csrf(page),
    },
    data: { username: pending, password, email: `${pending}@example.com` },
  })
  expect(response.status()).toBe(201)
  const receipt = await response.json()
  await page.goto(receipt.preview_url)
  await page.getByRole('button', { name: 'Verify email', exact: true }).click()
  await expect(
    page.getByText(
      'Email verified. Your current session is unchanged. Sign out to sign in to the newly verified account.',
    ),
  ).toBeVisible()
  expect(
    (await (await page.request.get('/api/auth/session')).json()).user.username,
  ).toBe(existing)
})
