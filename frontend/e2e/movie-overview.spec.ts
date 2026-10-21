import { memberTest as test, expect } from './fixtures'

const film = {
  id: 27205,
  title: 'Inception',
  year: 2010,
  runtime_minutes: 148,
  language: 'English',
  genres: ['Science Fiction'],
  director: 'Christopher Nolan',
  cast: ['Leonardo DiCaprio'],
  overview: 'A dream heist.',
  tagline: '',
  cover_url: null,
  source: 'tmdb',
  artwork_kind: 'placeholder',
  detail_metadata: {
    version: 1,
    release_date: '2010-07-16',
    spoken_languages: ['English', 'French'],
    production_companies: ['Warner Bros.', 'Legendary Pictures'],
    production_countries: ['United States of America'],
    budget: 160000000,
    revenue: 839030630,
    vote_average: 8.4,
    vote_count: 30000,
    status: 'Released',
    original_title: 'Inception',
    cast_credits: [
      {
        name: 'Leonardo DiCaprio',
        character: 'Cobb',
        profile_url: 'https://image.tmdb.org/t/p/w185/actor.jpg',
      },
    ],
  },
}

test('overview displays financials, rating attribution and cast roles without mobile overflow', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.route('**/api/movies/27205', (route) =>
    route.fulfill({ json: film }),
  )
  await page.route('https://image.tmdb.org/t/p/w185/**', (route) =>
    route.abort(),
  )
  await page.goto('/movies/27205')
  await expect(
    page.getByRole('heading', { name: 'Film details', exact: true }),
  ).toBeVisible()
  await expect(page.getByText('July 16, 2010', { exact: true })).toBeVisible()
  await expect(page.getByText('$160,000,000', { exact: true })).toBeVisible()
  await expect(page.getByText('$839,030,630', { exact: true })).toBeVisible()
  await expect(page.getByText('TMDB rating', { exact: true })).toBeVisible()
  await expect(page.getByText('30,000 votes', { exact: true })).toBeVisible()
  await expect(page.getByText('Warner Bros.', { exact: true })).toBeVisible()
  await expect(page.getByText('Cobb', { exact: true })).toBeVisible()
  await expect(page.locator('.cast-portrait-placeholder')).toBeVisible()
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true)
})

test('old movie responses remain usable and missing fields stay unknown', async ({
  page,
}) => {
  await page.route('**/api/movies/27205', (route) =>
    route.fulfill({ json: { ...film, detail_metadata: null } }),
  )
  await page.goto('/movies/27205')
  await expect(page.getByText('Not rated', { exact: true })).toBeVisible()
  await expect(page.getByText('Not reported', { exact: true })).toHaveCount(2)
  await expect(page.getByText('Role not listed', { exact: true })).toBeVisible()
  await expect(
    page.getByRole('heading', { name: 'Leonardo DiCaprio', exact: true }),
  ).toBeVisible()
})

test('section links support deep links, keyboard navigation and expandable cast', async ({
  page,
}) => {
  await page.route('**/api/movies/27205', (route) =>
    route.fulfill({
      json: {
        ...film,
        detail_metadata: {
          ...film.detail_metadata,
          cast_credits: Array.from({ length: 8 }, (_, i) => ({
            name: `Actor ${i}`,
            character: `Character ${i}`,
            profile_url: null,
          })),
        },
      },
    }),
  )
  await page.goto('/movies/27205#cast')
  await expect(
    page.getByRole('navigation', { name: 'Movie sections' }),
  ).toBeVisible()
  await expect(
    page.getByRole('navigation', { name: 'Movie sections' }).getByRole('link'),
  ).toHaveCount(4)
  await expect(
    page.getByRole('link', { name: 'Cast', exact: true }),
  ).toHaveCount(0)
  await expect(page.locator('#about #cast')).toBeVisible()
  await expect(
    page.getByRole('link', { name: 'Back to discovery', exact: true }),
  ).toHaveCount(0)
  await expect(
    page.getByRole('link', { name: 'About', exact: true }),
  ).toHaveAttribute('aria-current', 'location')
  await expect(page.locator('.cast-credit-card')).toHaveCount(6)
  await page.getByRole('button', { name: 'View all 8 cast members' }).click()
  await expect(page.locator('.cast-credit-card')).toHaveCount(8)
  await page.getByRole('link', { name: 'Quiz', exact: true }).focus()
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/#quiz$/)
  await expect(
    page.getByText('A quiz has not been prepared for this film yet.'),
  ).toBeVisible()
  expect(
    await page
      .locator('#quiz')
      .evaluate((el) => el.getBoundingClientRect().top),
  ).toBeGreaterThanOrEqual(70)
  await page.mouse.wheel(0, -400)
  await page.getByRole('link', { name: 'Quiz', exact: true }).click()
  expect(
    await page
      .locator('#quiz')
      .evaluate((el) => el.getBoundingClientRect().top),
  ).toBeGreaterThanOrEqual(70)
  await page.reload()
  await expect(
    page.getByText('A quiz has not been prepared for this film yet.'),
  ).toBeVisible()
  await expect(page.getByRole('tab')).toHaveCount(0)
})

test('saved content waits for the section and navigation preserves a discussion draft', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 })
  let quizReads = 0
  await page.route('**/api/movies/157336/quiz?*', (route) => {
    quizReads++
    return route.fulfill({ status: 503, json: {} })
  })
  await page.goto('/movies/157336')
  await expect(
    page.getByRole('heading', { name: 'Interstellar', exact: true }),
  ).toBeVisible()
  await page.waitForTimeout(250)
  expect(quizReads).toBe(0)
  await page.getByRole('switch', { name: 'Allow spoilers' }).check()
  await page.getByRole('link', { name: 'Discuss', exact: true }).click()
  await page
    .getByLabel('Your question')
    .fill('Why was this scene filmed this way?')
  await page.getByRole('link', { name: 'About', exact: true }).click()
  await page.getByRole('link', { name: 'Discuss', exact: true }).click()
  await expect(page.getByLabel('Your question')).toHaveValue(
    'Why was this scene filmed this way?',
  )
  await page.getByRole('switch', { name: 'Allow spoilers' }).uncheck()
  await expect(page.getByLabel('Your question')).toHaveValue('')
})

test('trailer loads only after a click, closes with Escape and restores keyboard focus', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 })
  let embeds = 0
  await page.route('https://www.youtube-nocookie.com/**', (route) => {
    embeds++
    return route.fulfill({
      contentType: 'text/html',
      body: '<p>Trailer player fixture</p>',
    })
  })
  await page.route('**/api/movies/27205', (route) =>
    route.fulfill({
      json: {
        ...film,
        detail_metadata: {
          ...film.detail_metadata,
          presentation_version: 1,
          trailer: {
            name: 'Official trailer',
            youtube_key: 'YoHD9XEInc0',
            official: true,
          },
          creative_credits: [
            { name: 'Christopher Nolan', role: 'Writer' },
            { name: 'Hans Zimmer', role: 'Composer' },
            { name: 'Wally Pfister', role: 'Cinematographer' },
          ],
        },
      },
    }),
  )
  await page.goto('/movies/27205')
  const watch = page.getByRole('button', { name: 'Watch trailer', exact: true })
  await expect(watch).toBeVisible()
  expect(embeds).toBe(0)
  await expect(page.locator('iframe')).toHaveCount(0)
  await watch.focus()
  await page.keyboard.press('Enter')
  await expect(
    page.getByRole('dialog', { name: 'Inception', exact: true }),
  ).toBeVisible()
  for (const viewport of [
    { width: 1440, height: 1000 },
    { width: 375, height: 812 },
    { width: 667, height: 375 },
  ]) {
    await page.setViewportSize(viewport)
    const rect = await page
      .getByRole('dialog', { name: 'Inception', exact: true })
      .boundingBox()
    expect(rect).not.toBeNull()
    expect(
      Math.abs(rect!.x + rect!.width / 2 - viewport.width / 2),
    ).toBeLessThan(2)
    expect(
      Math.abs(rect!.y + rect!.height / 2 - viewport.height / 2),
    ).toBeLessThan(2)
    expect(rect!.y).toBeGreaterThanOrEqual(15)
  }
  await page.setViewportSize({ width: 375, height: 812 })
  await expect(page.locator('iframe')).toHaveAttribute(
    'src',
    'https://www.youtube-nocookie.com/embed/YoHD9XEInc0?autoplay=1',
  )
  await expect.poll(() => embeds).toBe(1)
  await expect(
    page.getByRole('button', { name: 'Close trailer' }),
  ).toBeFocused()
  await expect(
    page.getByRole('link', { name: 'Watch on YouTube' }),
  ).toHaveAttribute('href', 'https://www.youtube.com/watch?v=YoHD9XEInc0')
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true)
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.locator('iframe')).toHaveCount(0)
  await expect(watch).toBeFocused()
  await watch.click()
  await page.getByRole('button', { name: 'Close trailer' }).click()
  await expect(page.locator('iframe')).toHaveCount(0)
  await page.getByRole('link', { name: 'About', exact: true }).click()
  await expect(
    page.getByRole('heading', { name: 'Creative team' }),
  ).toBeVisible()
  await expect(page.getByText('Hans Zimmer', { exact: true })).toBeVisible()
  await expect(page.getByText('Wally Pfister', { exact: true })).toBeVisible()
  await expect(page.getByText('Cinematographer', { exact: true })).toBeVisible()
})

test('legacy metadata hides unavailable media and untrusted trailer identifiers are rejected', async ({
  page,
}) => {
  await page.route('**/api/movies/27205', (route) =>
    route.fulfill({ json: film }),
  )
  await page.goto('/movies/27205')
  await expect(
    page.getByRole('heading', { name: 'Inception', exact: true }),
  ).toBeVisible()
  await expect(page.getByRole('button', { name: 'Watch trailer' })).toHaveCount(
    0,
  )
  await expect(
    page.getByRole('heading', { name: 'Creative team' }),
  ).toHaveCount(0)
  await page.unroute('**/api/movies/27205')
  await page.route('**/api/movies/27205', (route) =>
    route.fulfill({
      json: {
        ...film,
        detail_metadata: {
          ...film.detail_metadata,
          trailer: {
            name: 'Bad media',
            youtube_key: 'https://evil.example/embed',
            official: true,
          },
        },
      },
    }),
  )
  await page.reload()
  await expect(
    page.getByRole('heading', { name: 'The collection is taking a break.' }),
  ).toBeVisible()
  await expect(page.locator('iframe')).toHaveCount(0)
})
