import { test, expect } from './fixtures'

test('language filter survives navigation and clears correctly', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/')
  const language = page.getByLabel('Language', { exact: true })
  await language.selectOption('Korean')
  await expect(page).toHaveURL(/language=Korean/)
  await expect(page.locator('.movie-card')).toHaveCount(1)
  await page
    .getByRole('link', { name: 'Explore Parasite', exact: true })
    .click()
  await expect(page).toHaveURL(/\/movies\/496243$/)
  await page.getByRole('link', { name: 'Discover', exact: true }).click()
  await expect(language).toHaveValue('Korean')
  await page.reload()
  await expect(language).toHaveValue('Korean')
  await expect(page.locator('.movie-card')).toHaveCount(1)
  await page.getByLabel('Maximum runtime').selectOption('120')
  await expect(
    page.getByRole('heading', { name: 'No films found just yet.' }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Clear filters', exact: true }).click()
  await expect(page.locator('.movie-card')).toHaveCount(10)
  await expect(language).toHaveValue('')
  await expect(page).not.toHaveURL(/language=/)
  await language.selectOption('Japanese')
  await expect(page.locator('.movie-card')).toHaveCount(1)
  await expect(
    page.getByRole('link', { name: 'Explore Spirited Away', exact: true }),
  ).toBeVisible()
  await language.selectOption('')
  await expect(page.locator('.movie-card')).toHaveCount(10)
  await expect(page).not.toHaveURL(/language=/)
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true)
})

test('actor search, filters, movie route, and back state', async ({ page }) => {
  await page.goto('/')
  await page
    .getByRole('searchbox', { name: 'Find your next film' })
    .fill('Amy Adams')
  await expect(page.getByRole('searchbox')).toHaveValue('Amy Adams')
  await page.getByRole('button', { name: 'Search', exact: true }).click()
  await expect(page).toHaveURL(/q=Amy\+Adams/)
  await expect(page.locator('.movie-card')).toHaveCount(1)
  await page
    .getByLabel('Genre', { exact: true })
    .selectOption('Science Fiction')
  await expect(page).toHaveURL(/q=Amy\+Adams.*genre=Science\+Fiction/)
  await page.getByLabel('Maximum runtime').selectOption('120')
  await expect(
    page.getByRole('link', { name: 'Explore Arrival', exact: true }),
  ).toBeVisible()
  await expect(page.locator('.movie-card')).toHaveCount(1)
  await page.getByRole('link', { name: 'Explore Arrival', exact: true }).click()
  await expect(page).toHaveURL(/\/movies\/329865$/)
  await expect(
    page.getByRole('heading', { name: 'Arrival', exact: true, level: 1 }),
  ).toBeVisible()
  await page.goBack()
  await expect(page.getByRole('searchbox')).toHaveValue('Amy Adams')
  await expect(page.getByLabel('Genre', { exact: true })).toHaveValue(
    'Science Fiction',
  )
  await expect(page.getByLabel('Maximum runtime')).toHaveValue('120')
  await expect(page.locator('.movie-card')).toHaveCount(1)
  await page.getByRole('link', { name: 'Explore Arrival', exact: true }).click()
  await page.getByRole('link', { name: 'Discover', exact: true }).click()
  await expect(page.getByRole('searchbox')).toHaveValue('Amy Adams')
})

test('collection survives navigation, and removal is deliberate', async ({
  page,
}) => {
  await page.goto('/')
  await page
    .getByRole('button', { name: 'Save Arrival to collection', exact: true })
    .click()
  await page.getByRole('button', { name: 'Done', exact: true }).click()
  await page.getByRole('link', { name: /Collections/ }).click()
  await expect(page.locator('.movie-card')).toHaveCount(1)
  await expect(
    page.getByRole('link', { name: 'Explore Arrival', exact: true }),
  ).toBeVisible()
  await page
    .getByRole('button', {
      name: 'Manage collections for Arrival',
      exact: true,
    })
    .click()
  await page
    .getByRole('button', { name: 'Remove from saved', exact: true })
    .click()
  await expect(
    page.getByRole('heading', { name: 'Start your film collection' }),
  ).toBeVisible()
})

test('guest member gates retain keyboard section navigation', async ({page}) => {
  await page.goto('/movies/157336')
  await expect(page.getByRole('switch', {name:'Allow spoilers'})).toHaveCount(0)
  const factsLink=page.getByRole('link',{name:'Facts',exact:true})
  await factsLink.focus()
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/#facts$/)
  await expect(factsLink).toHaveAttribute('aria-current','location')
  await expect(page.locator('#facts').getByRole('link',{name:'Sign in or create an account'})).toBeVisible()
  await page.getByRole('link',{name:'Quiz',exact:true}).click()
  await expect(page.locator('#quiz').getByRole('link',{name:'Sign in or create an account'})).toBeVisible()
})

test('no results, query text escaping, and recovery', async ({ page }) => {
  await page.goto('/?q=%3Cscript%3Ealert(1)%3C%2Fscript%3E')
  await expect(
    page.getByRole('heading', { name: 'No films found just yet.' }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Show all films' }).click()
  await expect(page.locator('.movie-card')).toHaveCount(10)
})

test('unknown IDs and invalid routes do not fabricate movies', async ({
  page,
}) => {
  await page.goto('/movies/999999999')
  await expect(
    page.getByRole('heading', { name: 'This film isn’t in the collection.' }),
  ).toBeVisible()
  await page.goto('/movies/not-a-number')
  await expect(
    page.getByRole('heading', { name: 'This film isn’t in the collection.' }),
  ).toBeVisible()
})

test('backend failure has a working retry action', async ({ page }) => {
  await page.route('**/api/search/catalog*', (route) =>
    route.fulfill({ status: 503, body: '{}' }),
  )
  await page.goto('/')
  await expect(
    page.getByRole('heading', { name: 'The collection is taking a break.' }),
  ).toBeVisible()
  await page.unroute('**/api/search/catalog*')
  await page.getByRole('button', { name: 'Try again' }).click()
  await expect(page.locator('.movie-card')).toHaveCount(10)
})

test('corrupt browser storage recovers on a deliberate save', async ({
  page,
}) => {
  await page.addInitScript(() =>
    localStorage.setItem('frame.demo.collection.v1', '{broken json'),
  )
  await page.goto('/')
  await expect(page.locator('.storage-warning')).toHaveCount(0)
  await page
    .getByRole('button', { name: 'Save Arrival to collection', exact: true })
    .click()
  expect(
    await page.evaluate(() => localStorage.getItem('frame.demo.collection.v1')),
  ).toBeNull()
  await expect(page.getByRole('checkbox', { name: /All saved/ })).toBeChecked()
})

test('mobile layout, illustration assets, and reduced motion', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/')
  await expect(page.locator('.movie-card')).toHaveCount(10)
  await page.locator('.site-footer').scrollIntoViewIfNeeded()
  await expect
    .poll(() =>
      page
        .locator('.movie-card img')
        .evaluateAll((images) =>
          images.every(
            (image) =>
              (image as HTMLImageElement).complete &&
              (image as HTMLImageElement).naturalWidth > 0,
          ),
        ),
    )
    .toBe(true)
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true)
  expect(
    await page
      .getByRole('button', { name: 'Save Arrival to collection', exact: true })
      .evaluate((element) => getComputedStyle(element).transitionDuration),
  ).toBe('0s')
  await page.goto('/movies/120467')
  await expect(
    page.getByRole('heading', {
      name: 'The Grand Budapest Hotel',
      exact: true,
    }),
  ).toBeVisible()
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true)
})
