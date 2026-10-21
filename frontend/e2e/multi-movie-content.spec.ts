import { readFileSync } from 'node:fs'
import { expect, memberTest as test } from './fixtures'

// UI contract fixtures use authored banks; evidence correctness is checked separately.
for (const movieId of [
  27205, 329865, 603, 546554, 37165, 496243, 129, 120467, 438631, 155,
]) {
  test(`saved facts and story quiz for movie ${movieId} need no generation`, async ({
    page,
  }) => {
    const bank = JSON.parse(
      readFileSync(
        new URL(
          `../../backend/src/movie_companion/content_banks/${movieId}.json`,
          import.meta.url,
        ),
        'utf8',
      ),
    )
    const citation = {
      passage_id: 'fixture',
      source_label: 'Wikipedia fixture',
      source_ref: 'https://en.wikipedia.org/w/index.php?oldid=123',
      revision: 'fixture',
      excerpt: 'Authored UI fixture, not a truth benchmark.',
    }
    const envelope = {
      status: 'ready',
      message: 'Saved collection',
      prepared_at: '2026-10-11T00:00:00Z',
      content_version: 'reviewed-multi-movie-v1',
    }
    const quiz = {
      ...envelope,
      can_generate_more: false,
      items: bank.quiz.map(({ evidence_markers: _, ...item }: any) => ({
        ...item,
        citations: [citation],
      })),
    }
    const facts = {
      ...envelope,
      reading_sources: [],
      items: bank.facts.map(({ evidence_markers: _, ...item }: any) => ({
        ...item,
        citations: [citation],
      })),
    }
    let reads = 0
    let writes = 0
    // This film is outside the ten-film offline metadata demo. Mock only its
    // presentation; the same generic panels must still render its saved bank.
    if (movieId === 155) {
      await page.route('**/api/movies/155', (route) =>
        route.fulfill({
          json: {
            id: 155,
            title: 'The Dark Knight',
            year: 2008,
            runtime_minutes: 152,
            language: 'English',
            genres: ['Action', 'Crime', 'Drama'],
            director: 'Christopher Nolan',
            cast: ['Christian Bale', 'Heath Ledger'],
            overview: 'Batman, Gordon and Dent confront the Joker in Gotham.',
            tagline: '',
            cover_url: null,
            source: 'tmdb',
            artwork_kind: 'placeholder',
          },
        }),
      )
    }
    // History writes are expected; viewing a saved bank must not generate content.
    page.on('request', (request) => {
      if (
        /\/api\/movies\/[0-9]+\/(?:quiz|facts|preparation)/.test(
          request.url(),
        ) &&
        request.method() === 'POST'
      )
        writes++
    })
    await page.route(`**/api/movies/${movieId}/features`, (route) =>
      route.fulfill({
        json: { movie_id: movieId, facts: true, quiz: true, discussion: true },
      }),
    )
    for (const [kind, payload] of [
      ['quiz', quiz],
      ['facts', facts],
    ] as const) {
      await page.route(`**/api/movies/${movieId}/${kind}?*`, async (route) => {
        reads++
        expect(route.request().method()).toBe('GET')
        await route.fulfill({ json: payload })
      })
    }
    await page.goto(`/movies/${movieId}#facts`)
    await expect(page.locator('.fact-card')).toHaveCount(0)
    await page.getByRole('switch', { name: 'Allow spoilers' }).check()
    await expect(page.locator('.fact-card')).toHaveCount(5)
    await expect(
      page.getByText(bank.facts[0].title, { exact: true }),
    ).toBeVisible()
    await page.getByRole('link', { name: 'Quiz', exact: true }).click()
    await expect(page.locator('.quiz-card')).toHaveCount(10)
    const first = page.locator('.quiz-card').first()
    await first.getByRole('button').nth(bank.quiz[0].correct_index).click()
    await expect(first.getByText('Correct', { exact: true })).toBeVisible()
    await expect(first.getByText('Why this answer?')).toHaveCount(0)
    await expect(page.locator('.quiz-score')).toContainText('1 / 10')
    await expect(
      page.locator('.quiz-bottom-actions button').last(),
    ).toBeDisabled()
    expect(writes).toBe(0)
    await page.reload()
    await expect(page.locator('.quiz-card')).toHaveCount(10)
    await expect(page.locator('.quiz-score')).toContainText('0 / 10')
    expect(reads).toBeGreaterThanOrEqual(3)
    expect(writes).toBe(0)
  })
}
