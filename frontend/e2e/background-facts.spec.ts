import { memberTest as test, expect } from './fixtures'

test('interview and craft sources have correct attribution and safe links on mobile', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.route('**/api/movies/329865/features', (route) =>
    route.fulfill({
      json: { movie_id: 329865, discussion: true, quiz: true, facts: true },
    }),
  )
  const time = 'https://time.com/4677598/arrival-oscar-cinematography/'
  const bfi =
    'https://www.bfi.org.uk/features/strange-new-worlds-craft-denis-villeneuve'
  await page.route('**/api/movies/329865/facts?*', (route) =>
    route.fulfill({
      json: {
        status: 'ready',
        message: 'Saved',
        items: [
          {
            id: 'external',
            title: 'A photographer behind the atmosphere',
            text: 'An authored production detail with supporting interview evidence.',
            citations: [
              {
                passage_id: 'p1',
                source_label: 'TIME · Interview',
                source_ref: time,
                revision: 'v1',
                excerpt: 'Authored source evidence.',
              },
            ],
          },
        ],
        reading_sources: [
          {
            kind: 'interview',
            title: 'A cinematographer’s perspective',
            source_ref: time,
            publisher: 'TIME',
            date: '2017-02-22',
            authors: ['Authored author'],
            note: 'Interview and production context.',
            retrieved_at: '2026-10-11T00:00:00Z',
            content_sha256: 'a'.repeat(64),
          },
          {
            kind: 'article',
            title: 'The craft of the film',
            source_ref: bfi,
            publisher: 'BFI',
            date: '2021-09-22',
            authors: ['Authored author'],
            note: 'Film craft.',
            retrieved_at: '2026-10-11T00:00:00Z',
            content_sha256: 'b'.repeat(64),
          },
        ],
      },
    }),
  )
  await page.goto('/movies/329865#facts')
  await page.getByRole('switch', { name: 'Allow spoilers' }).check()
  await expect(
    page.getByRole('heading', { name: 'A photographer behind the atmosphere' }),
  ).toBeVisible()
  await page.getByText('Source & context', { exact: true }).click()
  await expect(
    page.getByRole('link', { name: 'View source', exact: true }),
  ).toHaveAttribute('href', time)
  const interview = page.getByRole('link', {
    name: /A cinematographer’s perspective/,
  })
  await expect(interview).toContainText('Interview · 2017')
  await expect(interview).toHaveAttribute('href', time)
  await expect(interview).toHaveAttribute('rel', 'noopener noreferrer')
  await expect(
    page.getByRole('link', { name: /The craft of the film/ }),
  ).toContainText('Film craft · 2021')
  await expect(page.locator('#facts .feature-credit')).toContainText(
    'TIME, BFI',
  )
  await expect(
    page.getByRole('link', { name: 'Wikipedia attribution' }),
  ).toHaveCount(0)
  await expect(page.locator('#facts')).not.toContainText('CaltechAUTHORS')
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true)
})

test('a publisher lookalike URL is rejected by the API contract', async ({
  page,
}) => {
  await page.route('**/api/movies/329865/features', (route) =>
    route.fulfill({
      json: { movie_id: 329865, discussion: true, quiz: true, facts: true },
    }),
  )
  await page.route('**/api/movies/329865/facts?*', (route) =>
    route.fulfill({
      json: {
        status: 'ready',
        message: 'Saved',
        items: [
          {
            id: 'x',
            title: 'Unsafe link',
            text: 'Authored fixture.',
            citations: [
              {
                passage_id: 'x',
                source_label: 'TIME',
                source_ref:
                  'https://time.com.evil.example/4677598/arrival-oscar-cinematography/',
                revision: 'v1',
                excerpt: 'Authored evidence.',
              },
            ],
          },
        ],
      },
    }),
  )
  await page.goto('/movies/329865#facts')
  await page.getByRole('switch', { name: 'Allow spoilers' }).check()
  await expect(page.locator('#facts [role="alert"]')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Unsafe link' })).toHaveCount(
    0,
  )
})
