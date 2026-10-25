import { memberTest as test, expect } from './fixtures'

test('question panel scopes permission, posts input, renders citations and erases on preference change', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 })
  let calls = 0
  await page.route('**/api/movies/157336/questions', async (route) => {
    calls++
    expect(route.request().postDataJSON()).toEqual({
      question: 'How was the sound made?',
      allow_spoilers: true,
    })
    await route.fulfill({
      json: {
        status: 'answered',
        answer: 'Authored fixture answer.',
        citations: [
          {
            passage_id: 'fixture',
            source_label: 'Wikipedia fixture',
            source_ref: 'https://en.wikipedia.org/w/index.php?oldid=123',
            revision: 'v1',
            excerpt: 'Authored supporting fixture.',
          },
        ],
      },
    })
  })
  await page.goto('/movies/157336')
  await page.getByRole('link', { name: 'Discuss' }).click()
  await expect(
    page.getByRole('button', { name: 'Ask PlotSpot' }),
  ).toBeDisabled()
  expect(calls).toBe(0)
  await page.getByRole('switch', { name: 'Allow spoilers' }).check()
  await page.getByLabel('Your question').fill('How was the sound made?')
  await page.getByRole('button', { name: 'Ask PlotSpot' }).click()
  await expect(page.getByText('Authored fixture answer.')).toBeVisible()
  await page.getByText('Source 1 · Wikipedia fixture').click()
  await expect(page.getByText('Authored supporting fixture.')).toBeVisible()
  await expect(
    page.getByRole('link', { name: 'Read this source revision' }),
  ).toHaveAttribute('href', 'https://en.wikipedia.org/w/index.php?oldid=123')
  await page.screenshot({
    path: '../.cache/previews/movie-questions-mobile.png',
    fullPage: true,
  })
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.screenshot({
    path: '../.cache/previews/movie-questions-desktop.png',
    fullPage: true,
  })
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true)
  await page.setViewportSize({ width: 375, height: 812 })
  await page.getByRole('switch', { name: 'Allow spoilers' }).uncheck()
  await expect(page.getByText('Authored fixture answer.')).toHaveCount(0)
  await expect(page.getByLabel('Your question')).toBeDisabled()
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true)
})

test('question errors are recoverable and pending request can be cancelled', async ({
  page,
}) => {
  await page.route('**/api/movies/157336/questions', (route) =>
    route.fulfill({ status: 503, json: { detail: 'Test unavailable' } }),
  )
  await page.goto('/movies/157336')
  await page.getByRole('switch', { name: 'Allow spoilers' }).check()
  await page.getByRole('link', { name: 'Discuss' }).click()
  await page.getByLabel('Your question').fill('A question')
  await page.getByRole('button', { name: 'Ask PlotSpot' }).click()
  await expect(page.getByRole('alert')).toContainText('service is unavailable')
  await expect(page.getByRole('button', { name: 'Ask PlotSpot' })).toBeEnabled()
  await page.unroute('**/api/movies/157336/questions')
  let release: () => void = () => {}
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route('**/api/movies/157336/questions', async (route) => {
    await gate
    await route.fulfill({ status: 503, json: {} }).catch(() => {})
  })
  await page.getByRole('button', { name: 'Ask PlotSpot' }).click()
  await expect(
    page.getByRole('button', { name: 'Cancel request' }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Cancel request' }).click()
  release()
  await expect(page.getByRole('alert')).toContainText('cancelled')
})

test('another supported movie can ask scoped questions and shows missing collections honestly', async ({
  page,
}) => {
  let calls = 0
  await page.route('**/api/movies/329865/questions', async (route) => {
    calls++
    expect(route.request().postDataJSON()).toEqual({
      question: 'Who directed Arrival?',
      allow_spoilers: true,
    })
    await route.fulfill({
      json: {
        status: 'answered',
        answer: 'Authored fixture: Denis Villeneuve directed Arrival.',
        citations: [
          {
            passage_id: 'arrival',
            source_label: 'Wikipedia Arrival fixture',
            source_ref: 'https://en.wikipedia.org/w/index.php?oldid=456',
            revision: 'arrival-fixture',
            excerpt: 'Authored Arrival evidence.',
          },
        ],
      },
    })
  })
  await page.goto('/movies/329865')
  await page.getByRole('link', { name: 'Discuss', exact: true }).click()
  await expect(
    page.getByRole('textbox', { name: 'Your question' }),
  ).toBeDisabled()
  expect(calls).toBe(0)
  await page.getByRole('switch', { name: 'Allow spoilers' }).check()
  await page
    .getByRole('button', { name: 'Who directed Arrival?', exact: true })
    .click()
  await page.getByRole('button', { name: 'Ask PlotSpot', exact: true }).click()
  await expect(
    page.getByText('Authored fixture: Denis Villeneuve directed Arrival.', {
      exact: true,
    }),
  ).toBeVisible()
  await page.getByRole('link', { name: 'Quiz', exact: true }).click()
  await expect(
    page.getByText('A quiz has not been prepared for this film yet.', {
      exact: true,
    }),
  ).toBeVisible()
  await page.getByRole('link', { name: 'Facts' }).click()
  await expect(
    page.getByText('Facts have not been prepared for this film yet.', {
      exact: true,
    }),
  ).toBeVisible()
})

test('feature inventory failure preserves metadata and can recover', async ({
  page,
}) => {
  await page.route('**/api/movies/329865/features', (route) =>
    route.fulfill({ status: 503, json: {} }),
  )
  await page.goto('/movies/329865')
  await expect(
    page.getByRole('heading', { name: 'Arrival', exact: true }),
  ).toBeVisible()
  await page.getByRole('link', { name: 'Discuss', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText(
    'Feature availability could not be checked.',
  )
  await page.unroute('**/api/movies/329865/features')
  await page.route('**/api/movies/329865/features', (route) =>
    route.fulfill({
      json: { movie_id: 329865, discussion: true, quiz: false, facts: false },
    }),
  )
  await page
    .getByRole('button', { name: 'Retry features', exact: true })
    .click()
  await expect(
    page.getByRole('heading', { name: 'Go a little deeper.', exact: true }),
  ).toBeVisible()
})

test('script context is disclosed separately and interpretations stay unscored', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.route('**/api/movies/157336/questions', (route) =>
    route.fulfill({
      json: {
        status: 'answered',
        answer: 'One possible reading: the watch represents their connection.',
        answer_kind: 'interpretation',
        script_context: {
          source_ref: 'https://imsdb.com/scripts/Interstellar.html',
          version: '2008-03-12 early draft; released-film match unverified',
          released_film_verified: false,
        },
        citations: [
          {
            passage_id: 'watch',
            source_label: 'Wikipedia fixture',
            source_ref: 'https://en.wikipedia.org/w/index.php?oldid=123',
            revision: 'fixture',
            excerpt: 'Authored watch evidence.',
          },
        ],
      },
    }),
  )
  await page.goto('/movies/157336')
  await page.getByRole('switch', { name: 'Allow spoilers' }).check()
  await page.getByRole('link', { name: 'Discuss', exact: true }).click()
  await page.getByLabel('Your question').fill('What could the watch represent?')
  await page.getByRole('button', { name: 'Ask PlotSpot', exact: true }).click()
  await expect(
    page.getByText('A possible interpretation, not a scored answer.', {
      exact: true,
    }),
  ).toBeVisible()
  await page.getByText('Script context', { exact: true }).click()
  await expect(page.getByText(/2008-03-12 early draft/)).toBeVisible()
  await expect(
    page.getByRole('link', { name: 'Read the script', exact: true }),
  ).toHaveAttribute('href', 'https://imsdb.com/scripts/Interstellar.html')
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true)
  await page.getByRole('switch', { name: 'Allow spoilers' }).uncheck()
  await expect(page.getByText('Script context', { exact: true })).toHaveCount(0)
})

test('unreviewed script URLs cannot become clickable discussion sources', async ({
  page,
}) => {
  await page.route('**/api/movies/157336/questions', (route) =>
    route.fulfill({
      json: {
        status: 'answered',
        answer: 'Untrusted fixture answer.',
        citations: [],
        script_context: {
          source_ref: 'https://evil.test/script',
          version: 'Invented',
          released_film_verified: false,
        },
      },
    }),
  )
  await page.goto('/movies/157336')
  await page.getByRole('switch', { name: 'Allow spoilers' }).check()
  await page.getByRole('link', { name: 'Discuss', exact: true }).click()
  await page.getByLabel('Your question').fill('A story question')
  await page.getByRole('button', { name: 'Ask PlotSpot', exact: true }).click()
  await expect(page.getByRole('alert')).toBeVisible()
  await expect(
    page.getByText('Untrusted fixture answer.', { exact: true }),
  ).toHaveCount(0)
  await expect(
    page.getByRole('link', { name: 'Read the script', exact: true }),
  ).toHaveCount(0)
})

test('verified acquired web citations render with honest coverage and no Wikipedia attribution', async ({
  page,
}) => {
  await page.route('**/api/movies/157336/questions', (route) =>
    route.fulfill({
      json: {
        status: 'answered',
        answer: 'An authored answer supported by a retained web page.',
        source_coverage: { degraded: true, source_count: 4 },
        citations: [
          {
            passage_id: 'web-fixture',
            source_label: 'Reviewed movie article',
            source_kind: 'web',
            source_verified: true,
            source_ref: 'https://cinema.example/film-story',
            revision: 'web-' + 'a'.repeat(64),
            excerpt: 'Authored supporting article evidence.',
          },
        ],
      },
    }),
  )
  await page.goto('/movies/157336#discuss')
  await page.getByRole('switch', { name: 'Allow spoilers' }).check()
  await page.getByLabel('Your question').fill('An authored question')
  await page.getByRole('button', { name: 'Ask PlotSpot' }).click()
  await expect(
    page.getByText('An authored answer supported by a retained web page.', {
      exact: true,
    }),
  ).toBeVisible()
  await expect(
    page.getByText(/Some web sources could not be verified/),
  ).toBeVisible()
  await page.getByText('Source 1 · Reviewed movie article').click()
  await expect(
    page.getByRole('link', { name: 'Read this source revision' }),
  ).toHaveAttribute('href', 'https://cinema.example/film-story')
  await expect(
    page.getByText('Source text: Wikipedia contributors.'),
  ).toHaveCount(0)
  await page.locator('.question-answer').scrollIntoViewIfNeeded()
  await page.screenshot({
    path: new URL(
      '../../.cache/previews/multi-source-discuss.png',
      import.meta.url,
    ).pathname,
  })
})

for (const [label, url, verified] of [
  ['unverified', 'https://cinema.example/article', false],
  ['private IP', 'https://10.0.0.1/secret', true],
  ['screenplay authority', 'https://imsdb.com/scripts/Interstellar.html', true],
] as const) {
  test(`acquired citation contract rejects ${label}`, async ({ page }) => {
    await page.route('**/api/movies/157336/questions', (route) =>
      route.fulfill({
        json: {
          status: 'answered',
          answer: 'An invalid cited answer.',
          citations: [
            {
              passage_id: 'unsafe',
              source_label: 'Unsafe citation',
              source_kind: 'web',
              source_verified: verified,
              source_ref: url,
              revision: 'web-' + 'a'.repeat(64),
              excerpt: 'Authored fake source.',
            },
          ],
        },
      }),
    )
    await page.goto('/movies/157336#discuss')
    await page.getByRole('switch', { name: 'Allow spoilers' }).check()
    await page.getByLabel('Your question').fill('A question')
    await page.getByRole('button', { name: 'Ask PlotSpot' }).click()
    await expect(page.locator('#discuss [role="alert"]')).toBeVisible()
    await expect(
      page.getByText('An invalid cited answer.', { exact: true }),
    ).toHaveCount(0)
  })
}
