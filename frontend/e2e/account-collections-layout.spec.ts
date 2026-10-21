import { test, expect } from './fixtures'

for (const viewport of [
  { width: 1440, height: 1000 },
  { width: 900, height: 900 },
  { width: 375, height: 812 },
]) {
  test(`account and footer are focused at ${viewport.width}px`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport)
    await page.goto('/')
    await page
      .getByRole('button', { name: 'Save Arrival to collection', exact: true })
      .click()
    await page.getByRole('button', { name: 'Done', exact: true }).click()
    await page
      .getByRole('navigation', { name: 'Main navigation' })
      .getByRole('link', { name: 'Sign in', exact: true })
      .click()
    await expect(page.getByLabel('Username', { exact: true })).toBeVisible()
    await expect(page.getByText(/temporary saves/i)).toHaveCount(0)
    await expect(
      page.locator('.guest-save-prompt, .account-aside, .account-import'),
    ).toHaveCount(0)
    const card = await page.locator('.account-card').boundingBox()
    const gutter = await page
      .locator('.header-inner')
      .evaluate(
        (el) =>
          el.getBoundingClientRect().left +
          parseFloat(getComputedStyle(el).paddingLeft),
      )
    expect(Math.abs(card!.x - gutter)).toBeLessThan(2)
    const pageWidth = await page
      .locator('.account-page')
      .evaluate(
        (el) =>
          el.getBoundingClientRect().width -
          parseFloat(getComputedStyle(el).paddingLeft) -
          parseFloat(getComputedStyle(el).paddingRight),
      )
    expect(Math.abs(card!.width - pageWidth)).toBeLessThan(2)
    const userBox = await page
      .getByLabel('Username', { exact: true })
      .boundingBox()
    const passwordBox = await page
      .getByLabel('Password', { exact: true })
      .boundingBox()
    if (viewport.width >= 768) {
      expect(Math.abs(userBox!.y - passwordBox!.y)).toBeLessThan(2)
      expect(passwordBox!.x).toBeGreaterThan(userBox!.x + userBox!.width)
    } else expect(passwordBox!.y).toBeGreaterThan(userBox!.y + userBox!.height)
    await page
      .getByRole('button', { name: 'Create account', exact: true })
      .first()
      .click()
    await expect(
      page.getByLabel('Email address', { exact: true }),
    ).toBeVisible()
    const emailBox = await page
      .getByLabel('Email address', { exact: true })
      .boundingBox()
    const registerUserBox = await page
      .getByLabel('Username', { exact: true })
      .boundingBox()
    const registerPasswordBox = await page
      .getByLabel('Password', { exact: true })
      .boundingBox()
    if (viewport.width >= 1100) {
      expect(Math.abs(emailBox!.y - registerUserBox!.y)).toBeLessThan(2)
      expect(
        Math.abs(registerPasswordBox!.y - registerUserBox!.y),
      ).toBeLessThan(2)
    }
    await expect(page.getByRole('contentinfo')).toHaveClass(/site-footer--dark/)
    await expect(page.getByRole('contentinfo')).not.toContainText(
      /Stay curious|For the love of film|THERE’S ALWAYS MORE TO A FILM|Movie Companion/,
    )
    await expect(
      page.getByRole('navigation', { name: 'Footer navigation' }),
    ).toBeVisible()
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true)
    await page.screenshot({
      path: `../.cache/proof/account-layout-${viewport.width}.png`,
      fullPage: true,
    })
  })
}

test('Collections has one All saved label and preserves legacy named-collection deep links', async ({
  page,
}) => {
  await page.goto('/collections')
  await expect(page.getByText('All saved', { exact: true })).toHaveCount(1)
  await expect(page.locator('.collection-result-count')).toHaveCount(0)
  await expect(
    page.getByText(/Guest saves clear on refresh|Your saves clear on refresh/i),
  ).toHaveCount(0)
  await expect(
    page.getByText(
      'Keep your favourites together. Temporary saves. Sign in to keep them after refresh.',
    ),
  ).toHaveCount(0)
  await page
    .getByRole('button', { name: 'New collection', exact: true })
    .click()
  await page.getByLabel('New collection name').fill('Weekend films')
  await page.getByRole('button', { name: 'Create', exact: true }).click()
  const id = new URL(page.url()).searchParams.get('collection')!
  // A legacy link must retain its selector and fragment through redirect.
  await page.evaluate((id) => {
    const a = document.createElement('a')
    a.href = `/collection?collection=${id}#library`
    a.textContent = 'Legacy collection fixture'
    document.querySelector('main')!.append(a)
  }, id)
  // Full navigation intentionally clears guest data; check the URL separately.
  await page.getByRole('link', { name: 'Legacy collection fixture' }).click()
  await expect(page).toHaveURL(`/collections?collection=${id}#library`)
  await expect(page.getByText('All saved', { exact: true })).toHaveCount(1)
  await page.getByRole('link', { name: 'Collections', exact: true }).click()
  await expect(page).toHaveURL('/collections')
})

test('Collections sign-in returns to the library and preserves explicit visit import', async ({
  page,
}) => {
  await page.goto('/')
  await page
    .getByRole('button', { name: 'Save Arrival to collection', exact: true })
    .click()
  await page.getByRole('button', { name: 'Done', exact: true }).click()
  await page.getByRole('link', { name: 'Collections', exact: true }).click()
  await page
    .locator('.collection-page .page-intro')
    .getByRole('link', { name: 'Sign in', exact: true })
    .click()
  await expect(page).toHaveURL(/\/account\?returnTo=\/collections$/)
  await expect(page.getByText(/temporary saves/i)).toHaveCount(0)
  const name = `layout_${crypto.randomUUID().slice(0, 12)}`
  const password = 'A test-only long passphrase!'
  const session = await (await page.request.get('/api/auth/session')).json()
  const headers = {
    Origin: new URL(page.url()).origin,
    'X-CSRF-Token': session.csrf_token,
  }
  const registered = await page.request.post('/api/auth/register', {
    headers,
    data: { username: name, email: `${name}@example.com`, password },
  })
  expect(registered.status()).toBe(201)
  const receipt = await registered.json()
  expect(
    (
      await page.request.post('/api/auth/verify-email', {
        headers,
        data: { token: receipt.preview_url.split('=')[1] },
      })
    ).ok(),
  ).toBe(true)
  await page.getByLabel('Username', { exact: true }).fill(name)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page
    .locator('form')
    .getByRole('button', { name: 'Sign in', exact: true })
    .click()
  await expect(page).toHaveURL('/collections')
  await page
    .getByRole('button', { name: 'Keep these saves', exact: true })
    .click()
  await expect(
    page.getByText('Saves added to your account', { exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('link', { name: 'Explore Arrival', exact: true }),
  ).toBeVisible()
  await page.reload()
  await expect(
    page.getByRole('link', { name: 'Explore Arrival', exact: true }),
  ).toBeVisible()
})
