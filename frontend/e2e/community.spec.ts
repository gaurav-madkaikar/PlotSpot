import { test, expect, signInMember } from './fixtures'
import type { Page } from '@playwright/test'
async function openMovie(page: Page) {
  await page.goto('/movies/157336#discuss')
  await expect(
    page.getByRole('heading', { name: 'Join the conversation' }),
  ).toBeVisible()
}
async function post(page: Page, title: string, body: string, spoilers = false) {
  await page.getByRole('button', { name: 'Start a discussion' }).click()
  await page.getByLabel('Discussion title').fill(title)
  await page.getByLabel('Your post', { exact: true }).fill(body)
  if (spoilers) await page.getByLabel('Contains spoilers').check()
  await page
    .getByRole('button', { name: 'Post discussion', exact: true })
    .click()
  await expect(
    page.getByText('Your post was added.', { exact: true }),
  ).toBeVisible()
}

test('guests do not request private features and sign-in returns to the selected section', async ({
  page,
}) => {
  const privateRequests: string[] = []
  page.on('request', (r) => {
    if (
      /\/api\/(community|movies\/\d+\/(features|facts|quiz|questions|threads))/.test(
        r.url(),
      )
    )
      privateRequests.push(r.url())
  })
  await page.goto('/movies/157336#quiz')
  await expect(page.locator('.member-feature-gate')).toHaveCount(3)
  await expect(
    page.getByRole('heading', { name: 'Interstellar', exact: true }),
  ).toBeVisible()
  expect(privateRequests).toEqual([])
  expect((await page.request.get('/api/movies/157336/quiz')).status()).toBe(401)
  await page
    .locator('#quiz')
    .getByRole('link', { name: 'Sign in or create an account' })
    .click()
  await expect(page).toHaveURL(/returnTo=%2Fmovies%2F157336%23quiz/)
  const username = `return_${crypto.randomUUID().slice(0, 12)}`
  await page
    .getByRole('button', { name: 'Create account', exact: true })
    .first()
    .click()
  await page.getByLabel('Username', { exact: true }).fill(username)
  await page
    .getByLabel('Email address', { exact: true })
    .fill(`${username}@example.com`)
  await page.getByLabel('Password', { exact: true }).fill('member123')
  await page
    .getByRole('button', { name: 'Create account', exact: true })
    .last()
    .click()
  await page.getByRole('link', { name: 'Open verification link' }).click()
  await page.getByRole('button', { name: 'Verify email', exact: true }).click()
  await expect(
    page.getByText('Email verified. You can sign in now.'),
  ).toBeVisible()
  await page.getByLabel('Username', { exact: true }).fill(username)
  await page.getByLabel('Password', { exact: true }).fill('member123')
  await page
    .locator('form')
    .getByRole('button', { name: 'Sign in', exact: true })
    .click()
  await expect(page).toHaveURL(/\/movies\/157336#quiz$/)
  await expect(page.locator('.member-feature-gate')).toHaveCount(0)
})

test('members create, reply, edit and remove plain-text conversations', async ({
  page,
  baseURL,
}) => {
  await signInMember(page, new URL(baseURL!).origin)
  await openMovie(page)
  const title = `A closer look ${crypto.randomUUID().slice(0, 8)}`
  await post(
    page,
    title,
    '<script>window.movieUnsafe = true</script> A different perspective.',
  )
  await page.getByRole('button', { name: title, exact: true }).click()
  await expect(
    page.getByText(
      '<script>window.movieUnsafe = true</script> A different perspective.',
      { exact: true },
    ),
  ).toBeVisible()
  expect(
    await page.evaluate(() => Reflect.get(window, 'movieUnsafe')),
  ).toBeUndefined()
  await page
    .getByRole('button', { name: 'Reply to discussion', exact: true })
    .click()
  await page.getByLabel('Your reply').fill('I noticed the same detail.')
  await page.getByRole('button', { name: 'Post reply', exact: true }).click()
  await expect(
    page.getByText('I noticed the same detail.', { exact: true }),
  ).toBeVisible()
  await page
    .locator('.community-post')
    .filter({ hasText: 'I noticed the same detail.' })
    .getByRole('button', { name: 'Edit post' })
    .click()
  await page
    .getByRole('dialog')
    .getByLabel('Your reply')
    .fill('The soundtrack made the scene memorable.')
  await page.getByRole('button', { name: 'Save changes', exact: true }).click()
  await expect(
    page.getByText('The soundtrack made the scene memorable.', { exact: true }),
  ).toBeVisible()
  for (const width of [1440, 375]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true)
    await page
      .locator('.community-panel')
      .screenshot({ path: `../.cache/previews/community-${width}.png` })
  }
  await page
    .locator('.community-post')
    .filter({ hasText: 'The soundtrack made the scene memorable.' })
    .getByRole('button', { name: 'Remove post' })
    .click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  await expect(
    page.getByText('The soundtrack made the scene memorable.', { exact: true }),
  ).toBeVisible()
  await page
    .locator('.community-post')
    .filter({ hasText: 'The soundtrack made the scene memorable.' })
    .getByRole('button', { name: 'Remove post' })
    .click()
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Remove post', exact: true })
    .click()
  await expect(
    page.getByText('This post was removed.', { exact: true }),
  ).toBeVisible()
  await page
    .locator('.community-post')
    .filter({ hasText: 'A different perspective.' })
    .getByRole('button', { name: 'Remove post' })
    .click()
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Remove post', exact: true })
    .click()
  await expect(
    page.getByRole('button', { name: title, exact: true }),
  ).toHaveCount(0)
})

test('spoiler conversations redact immediately and another member can report them', async ({
  page,
  baseURL,
  browser,
}) => {
  const origin = new URL(baseURL!).origin
  await signInMember(page, origin)
  await openMovie(page)
  const title = `Final scene ${crypto.randomUUID().slice(0, 8)}`
  const body = 'An ending detail only visible with permission.'
  await post(page, title, body, true)
  await expect(
    page.getByRole('button', { name: title, exact: true }),
  ).toHaveCount(0)
  await page.getByRole('switch', { name: 'Allow spoilers' }).check()
  await page.getByRole('button', { name: title, exact: true }).click()
  await expect(page.getByText(body, { exact: true })).toBeVisible()
  await page.getByRole('switch', { name: 'Allow spoilers' }).uncheck()
  await expect(page.getByText(body, { exact: true })).toHaveCount(0)
  const context = await browser.newContext({ baseURL })
  const second = await context.newPage()
  try {
    await signInMember(second, origin)
    await openMovie(second)
    await second.getByRole('switch', { name: 'Allow spoilers' }).check()
    await second.getByRole('button', { name: title, exact: true }).click()
    await expect(second.getByRole('button', { name: 'Edit post' })).toHaveCount(
      0,
    )
    await second.getByRole('button', { name: 'Report post' }).click()
    await second.getByLabel('Reason').selectOption('spoiler')
    await second
      .getByLabel('Details (optional)')
      .fill('Please review the spoiler label.')
    await second.getByRole('button', { name: 'Send report' }).click()
    await expect(
      second.getByText('Report sent for moderator review.'),
    ).toBeVisible()
  } finally {
    await context.close()
  }
})

test('moderator report controls confirm actions without revealing spoiler text', async ({
  page,
  baseURL,
}) => {
  const session = await signInMember(page, new URL(baseURL!).origin)
  await page.route('**/api/community/capabilities', (r) =>
    r.fulfill({ json: { viewer_id: session.user.id, moderator: true } }),
  )
  let hidden = false
  await page.route('**/api/community/reports?*', (r) =>
    r.fulfill({
      json: {
        viewer_id: session.user.id,
        page: 1,
        total: 1,
        has_more: false,
        items: [
          {
            id: 1,
            kind: 'thread',
            target_id: 1,
            movie_id: 157336,
            reason: 'spam',
            details: null,
            reporter: 'test_reporter',
            created_at: '2026-10-12T00:00:00Z',
            state: hidden ? 'resolved' : 'open',
            content_state: hidden ? 'hidden' : 'visible',
            title: null,
            body: null,
            spoilers: true,
            spoiler_locked: true,
            revision: hidden ? 2 : 1,
          },
        ],
      },
    }),
  )
  await page.route('**/api/community/reports/1/review', (r) => {
    expect(r.request().headers()['x-csrf-token']).toBe(session.csrf_token)
    expect(r.request().postDataJSON().action).toBe('hide')
    hidden = true
    return r.fulfill({ json: { viewer_id: session.user.id, id: 1 } })
  })
  await openMovie(page)
  await expect(
    page.getByText('Enable spoilers to review this content.'),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Hide post', exact: true }).click()
  await expect(
    page.getByRole('dialog', { name: 'Confirm review' }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Confirm', exact: true }).click()
  await expect(
    page.getByRole('button', { name: 'Restore post', exact: true }),
  ).toBeVisible()
})

test('member content and drafts disappear when the account session changes to guest', async ({
  page,
  baseURL,
}) => {
  await signInMember(page, new URL(baseURL!).origin)
  await openMovie(page)
  const title = `Member view ${crypto.randomUUID().slice(0, 8)}`
  await post(page, title, 'A member-only conversation.')
  await page.getByRole('button', { name: title, exact: true }).click()
  await expect(
    page.getByText('A member-only conversation.', { exact: true }),
  ).toBeVisible()
  await page
    .getByRole('button', { name: 'Reply to discussion', exact: true })
    .click()
  await page.getByLabel('Your reply').fill('An unsent reply.')
  await page.route('**/api/auth/session', (r) =>
    r.fulfill({ json: { user: null, csrf_token: 'x'.repeat(43) } }),
  )
  await page.evaluate(() => window.dispatchEvent(new Event('focus')))
  await expect(
    page
      .locator('#discuss')
      .getByRole('link', { name: 'Sign in or create an account' }),
  ).toBeVisible()
  await expect(
    page.getByText('A member-only conversation.', { exact: true }),
  ).toHaveCount(0)
  await expect(page.getByLabel('Your reply')).toHaveCount(0)
  await expect(
    page.getByRole('heading', { name: 'Interstellar', exact: true }),
  ).toBeVisible()
})
