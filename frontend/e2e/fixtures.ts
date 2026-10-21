import { test as base, expect } from '@playwright/test'

// Feature inventory fixtures are independent of the developer's private SQLite DB.
export const test = base.extend<{ featureInventory: void }>({
  featureInventory: [
    async ({ page, context }, use) => {
      // Isolate client throttling between tests; uvicorn trusts only our loopback
      // proxy. Production rate limits stay enabled and have separate backend tests.
      const clientIp = `192.0.${Math.floor(Math.random() * 254)}.${1 + Math.floor(Math.random() * 254)}`
      await context.setExtraHTTPHeaders({ 'X-Forwarded-For': clientIp })
      await page.route('**/api/movies/*/features', async (route) => {
        const id = Number(new URL(route.request().url()).pathname.split('/')[3])
        await route.fulfill({
          json: {
            movie_id: id,
            discussion: [
              27205, 157336, 329865, 603, 546554, 496243, 129, 37165, 120467,
              438631,
            ].includes(id),
            quiz: id === 157336,
            facts: id === 157336,
          },
        })
      })
      await page.route('**/api/watch-regions', (route) =>
        route.fulfill({
          json: {
            items: [
              { code: 'IN', name: 'India' },
              { code: 'US', name: 'United States' },
            ],
            checked_at: '2026-10-11T00:00:00Z',
            stale: false,
          },
        }),
      )
      await page.route('**/api/movies/*/watch?*', (route) => {
        const url = new URL(route.request().url())
        return route.fulfill({
          json: {
            movie_id: Number(url.pathname.split('/')[3]),
            country: url.searchParams.get('country'),
            status: 'unavailable',
            groups: [],
            watch_url: null,
            checked_at: '2026-10-11T00:00:00Z',
            stale: false,
          },
        })
      })
      await page.route('**/api/movies/*/related', (route) => {
        const id = Number(new URL(route.request().url()).pathname.split('/')[3])
        return route.fulfill({
          json: {
            movie_id: id,
            items: [],
            checked_at: '2026-10-11T00:00:00Z',
            stale: false,
          },
        })
      })
      await use()
    },
    { auto: true },
  ],
})
export { expect }

// Member-only UI suites use real registration/verification/cookies in the
// disposable browser-test database. Guest suites keep their anonymous context.
export async function signInMember(
  page: import('@playwright/test').Page,
  origin: string,
) {
  const username = `member_${crypto.randomUUID().slice(0, 16)}`
  const password = 'Local test password!'
  const session = await (await page.request.get('/api/auth/session')).json()
  const headers = { Origin: origin, 'X-CSRF-Token': session.csrf_token }
  const receipt = await page.request.post('/api/auth/register', {
    headers,
    data: { username, password, email: `${username}@example.com` },
  })
  expect(receipt.status()).toBe(201)
  const preview = (await receipt.json()).preview_url as string
  const token = new URL(preview, origin).hash.slice('#verify='.length)
  expect(
    (
      await page.request.post('/api/auth/verify-email', {
        headers,
        data: { token },
      })
    ).status(),
  ).toBe(200)
  const login = await page.request.post('/api/auth/login', {
    headers,
    data: { username, password },
  })
  expect(login.status()).toBe(200)
  return await login.json()
}
export const memberTest = test.extend<{ memberAccess: void }>({
  memberAccess: [
    async ({ page, baseURL, featureInventory }, use) => {
      void featureInventory
      await signInMember(page, new URL(baseURL!).origin)
      await use()
    },
    { auto: true },
  ],
})
