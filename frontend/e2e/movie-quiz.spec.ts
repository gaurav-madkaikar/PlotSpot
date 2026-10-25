import { expect, memberTest as test } from './fixtures'

const citation = {
  passage_id: 'fixture',
  source_label: 'Wikipedia fixture',
  source_ref: 'https://en.wikipedia.org/w/index.php?oldid=123',
  revision: 'fixture',
  excerpt: 'Authored supporting evidence.',
}
const quiz = {
  status: 'ready',
  message: 'Ready',
  items: [
    {
      id: 'dust',
      kind: 'plot',
      question: 'Where do the dust patterns lead?',
      options: ['A secret NASA facility', 'A school', 'Mars', 'A farm'],
      correct_index: 0,
      explanation: 'The coordinates lead to a secret NASA facility.',
      citations: [citation],
    },
    {
      id: 'mann',
      kind: 'plot',
      question: 'Why did Mann falsify his data?',
      options: [
        'To prove an equation',
        'To repair Earth',
        'In the hope of being rescued',
        'To stop time dilation',
      ],
      correct_index: 2,
      explanation: 'Mann hoped to be rescued.',
      citations: [citation],
    },
    ...Array.from({ length: 8 }, (_, i) => ({
      id: `story-${i}`,
      kind: 'plot',
      question: `Authored story question ${i + 3}?`,
      options: [`Answer ${i}`, `Other ${i}`, `Third ${i}`, `Fourth ${i}`],
      correct_index: 0,
      explanation: `Source-backed fixture explanation ${i}`,
      citations: [citation],
    })),
    {
      id: 'meaning',
      kind: 'interpretation',
      question: 'What might the watch represent?',
      options: ['Lost time', 'Connection', 'Curiosity', 'A promise'],
      correct_index: 1,
      explanation:
        'One reading is connection across time; other interpretations are possible.',
      citations: [citation],
    },
  ],
}

test('saved quiz auto-loads, permissions, score, reveal, source links and replay work on mobile', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 })
  let requests = 0
  await page.route('**/api/movies/157336/quiz?*', async (route) => {
    requests++
    expect(route.request().method()).toBe('GET')
    expect(
      new URL(route.request().url()).searchParams.get('allow_spoilers'),
    ).toBe('true')
    await route.fulfill({ json: quiz })
  })
  await page.goto('/movies/157336')
  await page.getByRole('link', { name: 'Quiz', exact: true }).click()
  await expect(
    page.getByRole('button', { name: 'Retry loading quiz' }),
  ).toHaveCount(0)
  expect(requests).toBe(0)
  await page.getByRole('switch', { name: 'Allow spoilers' }).check()
  await expect(
    page.getByText('The coordinates lead to a secret NASA facility.', {
      exact: true,
    }),
  ).toHaveCount(0)
  await page
    .getByRole('button', { name: 'A A secret NASA facility', exact: true })
    .click()
  await expect(page.getByText('Correct', { exact: true })).toBeVisible()
  await expect(page.getByText('Why this answer?')).toHaveCount(0)
  await page
    .getByRole('button', { name: 'A To prove an equation', exact: true })
    .click()
  await expect(
    page.getByText('Correct answer: Option C, In the hope of being rescued'),
  ).toBeVisible()
  await expect(page.locator('.quiz-score')).toContainText('1 / 10')
  const readsBeforeNavigation = requests
  await page.getByRole('link', { name: 'About', exact: true }).click()
  await page.getByRole('link', { name: 'Quiz', exact: true }).click()
  await expect(page.locator('.quiz-score')).toContainText('1 / 10')
  expect(requests).toBe(readsBeforeNavigation)
  await page.getByText('Why this answer?').first().click()
  await expect(
    page.getByText('Authored supporting evidence.').first(),
  ).toBeVisible()
  await expect(
    page.getByRole('link', { name: 'View source' }).first(),
  ).toHaveAttribute('href', citation.source_ref)
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true)
  await page.getByRole('button', { name: 'A Lost time', exact: true }).click()
  await expect(page.getByText('One possible reading')).toBeVisible()
  await expect(page.locator('.quiz-score')).toContainText('1 / 10')
  await expect(page.getByText('REFLECTION · UNSCORED')).toBeVisible()
  for (let i = 0; i < 8; i++)
    await page
      .getByRole('button', { name: `A Answer ${i}`, exact: true })
      .click()
  await expect(page.locator('.quiz-score')).toContainText('9 / 10')
  const readsBeforeReplay = requests
  await page.getByRole('button', { name: 'Play again' }).click()
  expect(requests).toBe(readsBeforeReplay)
  await expect(page.locator('.quiz-score')).toContainText('0 / 10')
  await expect(
    page.getByRole('button', { name: 'A A secret NASA facility', exact: true }),
  ).toBeEnabled()
  await page.getByRole('switch', { name: 'Allow spoilers' }).uncheck()
  await expect(
    page.getByText('Where do the dust patterns lead?', { exact: true }),
  ).toHaveCount(0)
})

test('quiz failure is recoverable and unsupported movies disclose coverage', async ({
  page,
}) => {
  await page.route('**/api/movies/157336/quiz?*', (route) =>
    route.fulfill({ status: 503, json: {} }),
  )
  await page.goto('/movies/157336')
  await page.getByRole('switch', { name: 'Allow spoilers' }).check()
  await page.getByRole('link', { name: 'Quiz', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText(
    'collection could not be loaded',
  )
  await expect(
    page.getByRole('button', { name: 'Retry loading quiz' }),
  ).toBeEnabled()
  await page.goto('/movies/27205')
  await page.getByRole('link', { name: 'Quiz', exact: true }).click()
  await expect(
    page.getByText('A quiz has not been prepared for this film yet.', {
      exact: false,
    }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: 'Retry loading quiz' }),
  ).toHaveCount(0)
})

test('production facts appear in facts section with source links and no quiz choices', async ({
  page,
}) => {
  await page.route('**/api/movies/157336/facts?*', (route) =>
    route.fulfill({
      json: {
        status: 'ready',
        message: 'Saved background, not live news.',
        items: Array.from({ length: 5 }, (_, i) => ({
          id: `fact-${i}`,
          title: `Production story ${i}`,
          text: `Interesting background fixture ${i}.`,
          citations: [citation],
        })),
      },
    }),
  )
  await page.goto('/movies/157336')
  await page.getByRole('link', { name: 'Facts' }).click()
  await expect(
    page.getByRole('button', { name: 'Retry loading facts' }),
  ).toHaveCount(0)
  await page.getByRole('switch', { name: 'Allow spoilers' }).check()
  await expect(
    page.getByText('Interesting background fixture 4.', { exact: true }),
  ).toBeVisible()
  const first = await page.locator('.fact-card').nth(0).boundingBox()
  const second = await page.locator('.fact-card').nth(1).boundingBox()
  expect(second!.x).toBe(first!.x)
  expect(second!.y).toBeGreaterThan(first!.y + first!.height)
  await expect(
    page
      .locator('#facts')
      .getByRole('group', { name: 'Answers to question 1' }),
  ).toHaveCount(0)
  await page.getByText('Source & context').first().click()
  await expect(
    page.getByRole('link', { name: 'View source' }).first(),
  ).toHaveAttribute('href', citation.source_ref)
})

test('generate more preserves answers and displays accepted questions', async ({
  page,
}) => {
  let saved = quiz
  await page.route('**/api/movies/157336/quiz?*', (route) =>
    route.fulfill({ json: saved }),
  )
  await page.route('**/api/movies/157336/quiz/more', async (route) => {
    expect(route.request().method()).toBe('POST')
    expect(route.request().postDataJSON()).toEqual({ allow_spoilers: true })
    saved = {
      ...quiz,
      message: '1 new question added.',
      items: [
        ...quiz.items.slice(0, -1),
        {
          id: 'bonus',
          kind: 'plot',
          question: 'Which robot collects the crucial data?',
          options: ['TARS', 'Mann', 'Cooper', 'Brand'],
          correct_index: 0,
          explanation: 'TARS collects the data.',
          citations: [citation],
        },
        quiz.items.at(-1)!,
      ],
    }
    await route.fulfill({ json: saved })
  })
  await page.goto('/movies/157336')
  await page.getByRole('switch', { name: 'Allow spoilers' }).check()
  await page.getByRole('link', { name: 'Quiz', exact: true }).click()
  await page
    .getByRole('button', { name: 'A A secret NASA facility', exact: true })
    .click()
  await page
    .getByRole('button', { name: 'Generate more questions', exact: true })
    .click()
  await expect(
    page.getByText('Which robot collects the crucial data?', { exact: true }),
  ).toBeVisible()
  await expect(page.locator('.quiz-score')).toContainText('1 / 11')
  await page.reload()
  await page.getByRole('switch', { name: 'Allow spoilers' }).check()
  await page.getByRole('link', { name: 'Quiz', exact: true }).click()
  await expect(
    page.getByText('Which robot collects the crucial data?', { exact: true }),
  ).toBeVisible()
})

test('failed expansion keeps the existing quiz usable', async ({ page }) => {
  await page.route('**/api/movies/157336/quiz?*', (route) =>
    route.fulfill({ json: quiz }),
  )
  await page.route('**/api/movies/157336/quiz/more', (route) =>
    route.fulfill({
      status: 502,
      json: {
        detail:
          'No new questions passed the source checks. Your saved quiz is unchanged.',
      },
    }),
  )
  await page.goto('/movies/157336')
  await page.getByRole('switch', { name: 'Allow spoilers' }).check()
  await page.getByRole('link', { name: 'Quiz', exact: true }).click()
  await page
    .getByRole('button', { name: 'Generate more questions', exact: true })
    .click()
  await expect(
    page.getByText(
      'No new questions passed the source checks. Your saved quiz is unchanged.',
      { exact: true },
    ),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: 'A A secret NASA facility', exact: true }),
  ).toBeEnabled()
  await expect(
    page.getByRole('button', { name: 'Generate more questions', exact: true }),
  ).toBeEnabled()
})

test('reviewed external facts render on mobile while script links stay outside facts', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 })
  const external = {
    ...citation,
    source_label: 'CaltechAUTHORS · Visual-effects account',
    source_ref: 'https://authors.library.caltech.edu/records/awp8p-s4d82',
    revision: 'caltech-' + 'a'.repeat(64),
  }
  const common = {
    authors: [],
    retrieved_at: '2026-10-10T00:00:00+00:00',
    content_sha256: 'a'.repeat(64),
  }
  await page.route('**/api/movies/157336/facts?*', (route) =>
    route.fulfill({
      json: {
        status: 'ready',
        message: 'Saved',
        items: [
          {
            id: 'renderer',
            title: 'A movie renderer became a research tool',
            text: 'Reviewed visual-effects background.',
            citations: [external],
          },
        ],
        reading_sources: [
          {
            ...common,
            kind: 'research',
            title: 'The science behind the visuals',
            source_ref: external.source_ref,
            publisher: 'CaltechAUTHORS · ACM',
            date: '2015-08',
            note: 'A published account from the visual-effects team.',
          },
          {
            ...common,
            kind: 'early_draft',
            title: 'Interstellar screenplay',
            source_ref: 'https://imsdb.com/scripts/Interstellar.html',
            publisher: 'IMSDb',
            date: '2008-03-12',
            note: 'Early draft. Story details differ from the released film.',
          },
        ],
      },
    }),
  )
  await page.goto('/movies/157336')
  await page.getByRole('switch', { name: 'Allow spoilers' }).check()
  await page.getByRole('link', { name: 'Facts' }).click()
  await expect(
    page.getByText('A movie renderer became a research tool', { exact: true }),
  ).toBeVisible()
  await page.getByText('Source & context').click()
  await expect(page.getByRole('link', { name: 'View source' })).toHaveAttribute(
    'href',
    external.source_ref,
  )
  const script = page.getByRole('link', { name: /Interstellar screenplay/ })
  await expect(script).toHaveCount(0)
  await expect(
    page.getByRole('link', { name: /The science behind the visuals/ }),
  ).toHaveAttribute('href', external.source_ref)
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true)
})

test('prepared quiz availability is driven by backend inventory rather than a fixed movie ID', async ({
  page,
}) => {
  await page.route('**/api/movies/27205/features', (route) =>
    route.fulfill({
      json: { movie_id: 27205, discussion: true, quiz: true, facts: false },
    }),
  )
  await page.route('**/api/movies/27205/quiz?*', (route) =>
    route.fulfill({ json: quiz }),
  )
  await page.goto('/movies/27205')
  await page.getByRole('switch', { name: 'Allow spoilers' }).check()
  await page.getByRole('link', { name: 'Quiz', exact: true }).click()
  await expect(
    page.getByText('Where do the dust patterns lead?', { exact: true }),
  ).toBeVisible()
})
