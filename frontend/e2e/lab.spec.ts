import { expect, test } from '@playwright/test'

const generatedAt = '2026-10-25T10:00:00Z'
const storyId = `story_${'a'.repeat(32)}`
const prepId = `prep_${'b'.repeat(32)}`

function metric(
  id: string,
  label: string,
  numerator: number,
  denominator: number,
  definition: string,
) {
  return {
    id,
    label,
    value: Math.round((numerator * 1000) / denominator) / 10,
    unit: 'percent',
    numerator,
    denominator,
    direction: 'higher',
    definition,
  }
}

const overview = {
  generated_at: generatedAt,
  status: 'partial',
  gated_passed: 2,
  gated_total: 2,
  held_out_passed: 13,
  held_out_total: 18,
  recent_successful_runs: 2,
  degraded_or_failed_runs: 0,
  suites: [
    {
      id: 'readiness_controls',
      title: 'Content readiness controls',
      feature: 'readiness',
      category: 'audit',
      status: 'pass',
      gated: true,
      recorded_at: generatedAt,
      metrics: [
        metric(
          'passed',
          'Readiness controls passed',
          17,
          17,
          'Recorded controls matching their expected decision.',
        ),
      ],
      source_label: 'evals/movie-rag/research/readiness-v5-final.json',
      limitations: ['Development controls are not production accuracy.'],
      warnings: [],
    },
    {
      id: 'twenty_film_audit',
      title: 'Twenty-film reviewability audit',
      feature: 'readiness',
      category: 'audit',
      status: 'pass',
      gated: true,
      recorded_at: generatedAt,
      metrics: [
        {
          id: 'movie_count',
          label: 'Movies audited',
          value: 20,
          unit: 'count',
          numerator: null,
          denominator: null,
          direction: 'neutral',
          definition: 'Movie banks included in the reviewability audit.',
        },
      ],
      source_label: 'evals/movie-rag/expanded-20/final-review-audit-v2.json',
      limitations: ['Integrity checks do not prove semantic correctness.'],
      warnings: [],
    },
    {
      id: 'content_quality_held_out',
      title: 'Structured content review · held-out',
      feature: 'retrieval',
      category: 'held_out',
      status: 'informational',
      gated: false,
      recorded_at: generatedAt,
      metrics: [
        metric(
          'label_matches',
          'Label agreement',
          7,
          12,
          'Decisions matching frozen labels.',
        ),
      ],
      source_label:
        'evals/movie-rag/content-quality-held-out-v2-structured-v3-ollama.json',
      limitations: ['Reserved synthetic cases; no external annotations.'],
      warnings: [],
    },
  ],
  features: ['search', 'facts', 'quiz', 'discuss'].map((feature) => ({
    feature,
    status: feature === 'quiz' ? 'partial' : 'healthy',
    stages: ['retrieval', 'generation', 'verification', 'publication'].map(
      (stage) => ({
        stage,
        status:
          feature === 'search' && stage !== 'retrieval'
            ? 'not_applicable'
            : stage === 'generation' && feature === 'quiz'
              ? 'no_data'
              : 'healthy',
        detail:
          feature === 'search' && stage !== 'retrieval'
            ? 'This stage does not apply to the feature.'
            : 'The registered gate passed.',
      }),
    ),
  })),
  warnings: [
    {
      code: 'missing_source',
      suite_id: null,
      message: 'One optional run source is unavailable.',
    },
  ],
  limitations: [
    'Informational reports are excluded from gated pass-rate denominators.',
    'Recent runs are bounded local records, not production monitoring.',
  ],
}

const runs = {
  items: [
    {
      id: storyId,
      movie_id: 27205,
      title: 'Inception',
      workflow: 'story_rag',
      state: 'completed',
      updated_at: generatedAt,
      duration_seconds: null,
      source_count: 2,
      retrieval_count: 5,
      degraded: false,
      warnings: [],
    },
    {
      id: prepId,
      movie_id: 157336,
      title: 'Interstellar',
      workflow: 'preparation',
      state: 'needs_review',
      updated_at: '2026-10-24T10:00:00Z',
      duration_seconds: null,
      source_count: 4,
      retrieval_count: 18,
      degraded: false,
      warnings: [],
    },
  ],
  warnings: [],
}

const detail = {
  ...runs.items[0],
  stages: [
    {
      name: 'index',
      status: 'completed',
      duration_seconds: null,
      count: 367,
      message: 'Reuse or prepare the scoped evidence index.',
    },
    {
      name: 'retrieve',
      status: 'completed',
      duration_seconds: null,
      count: 5,
      message: 'Rank movie-scoped plot and optional script passages.',
    },
    {
      name: 'generate',
      status: 'completed',
      duration_seconds: null,
      count: 2,
      message: 'Generate bounded story candidates.',
    },
    {
      name: 'verify',
      status: 'completed',
      duration_seconds: null,
      count: 1,
      message: 'Apply released-film and support checks.',
    },
  ],
}

async function installLabRoutes(
  page: import('@playwright/test').Page,
  options: { overviewFailure?: boolean } = {},
) {
  await page.route('**/api/lab/overview', (route) =>
    options.overviewFailure
      ? route.fulfill({ status: 503, json: {} })
      : route.fulfill({ json: overview }),
  )
  await page.route('**/api/lab/runs?*', (route) =>
    route.fulfill({ json: runs }),
  )
  await page.route(`**/api/lab/runs/${storyId}`, (route) =>
    route.fulfill({ json: detail }),
  )
}

test('lab explains metrics and opens an inline run timeline', async ({
  page,
}) => {
  await installLabRoutes(page)
  await page.goto('/lab')
  await expect(
    page.getByRole('heading', { name: 'AI Reliability Lab' }),
  ).toBeVisible()
  await expect(page.getByText('2 of 2 gated suites passing')).toBeVisible()
  await expect(
    page
      .getByRole('article')
      .filter({ hasText: 'Structured content review · held-out' })
      .getByText('Held-out', { exact: true }),
  ).toBeVisible()
  await page.getByRole('button', { name: /Inception.*Story RAG/i }).click()
  await expect(
    page.getByRole('heading', { name: 'Run timeline' }),
  ).toBeVisible()
  await expect(page.getByText('Retrieve', { exact: true })).toBeVisible()
  await expect(page.getByText('private question')).toHaveCount(0)
})

test('lab keeps partial data usable and has no mutation controls', async ({
  page,
}) => {
  await installLabRoutes(page)
  await page.goto('/lab')
  await expect(page.getByText('Some evidence is unavailable')).toBeVisible()
  await expect(
    page.getByRole('button', { name: /publish|delete|retry run|cancel/i }),
  ).toHaveCount(0)
  await page.getByLabel('Evidence category').selectOption('held_out')
  await expect(
    page.getByRole('heading', {
      name: 'Structured content review · held-out',
    }),
  ).toBeVisible()
  await expect(
    page.getByRole('heading', { name: 'Content readiness controls' }),
  ).toHaveCount(0)
})

test('lab fits a narrow viewport and supports keyboard run selection', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await installLabRoutes(page)
  await page.goto('/lab')
  const run = page.getByRole('button', { name: /Inception.*Story RAG/i })
  await run.focus()
  await page.keyboard.press('Enter')
  await expect(
    page.getByRole('heading', { name: 'Run timeline' }),
  ).toBeVisible()
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true)
})

test('lab provides a retry state when the overview is unavailable', async ({
  page,
}) => {
  await installLabRoutes(page, { overviewFailure: true })
  await page.goto('/lab')
  await expect(
    page.getByRole('heading', { name: 'Reliability data is unavailable' }),
  ).toBeVisible()
  await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible()
})
