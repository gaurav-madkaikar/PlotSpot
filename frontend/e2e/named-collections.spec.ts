import { test, expect } from './fixtures'

async function saveArrival(page: import('@playwright/test').Page) {
  await page
    .getByRole('button', { name: 'Save Arrival to collection', exact: true })
    .click()
}

test('a temporary film belongs to multiple collections and memberships are independent', async ({
  page,
}) => {
  await page.goto('/')
  await saveArrival(page)
  const picker = page.getByRole('dialog', { name: 'Arrival', exact: true })
  await expect(
    picker.getByRole('checkbox', { name: /All saved/ }),
  ).toBeChecked()
  for (const name of ['Weekend favourites', 'Science fiction']) {
    await picker.getByLabel('New collection name').fill(name)
    await picker.getByRole('button', { name: 'Create', exact: true }).click()
    await expect(picker.getByRole('checkbox', { name })).toBeChecked()
  }
  await picker.getByRole('button', { name: 'Done', exact: true }).click()
  await page.getByRole('link', { name: 'Collections', exact: true }).click()
  await expect(page).toHaveURL(/\/collections$/)
  await page.getByRole('link', { name: /Weekend favourites 1/ }).click()
  await page
    .getByRole('button', {
      name: 'Manage collections for Arrival',
      exact: true,
    })
    .click()
  await picker.getByRole('checkbox', { name: /Weekend favourites/ }).uncheck()
  await picker.getByRole('button', { name: 'Done', exact: true }).click()
  await expect(
    page.getByRole('heading', { name: 'No films in this collection' }),
  ).toBeVisible()
  await page.getByRole('link', { name: /Science fiction 1/ }).click()
  await expect(
    page.getByRole('link', { name: 'Explore Arrival', exact: true }),
  ).toBeVisible()
  await page.getByRole('link', { name: /All saved 1/ }).click()
  await page
    .getByRole('button', {
      name: 'Manage collections for Arrival',
      exact: true,
    })
    .click()
  await picker
    .getByRole('button', { name: 'Remove from saved', exact: true })
    .click()
  await expect(
    page.getByRole('heading', { name: 'Start your film collection' }),
  ).toBeVisible()
})

test('temporary collection names validate, rename and delete without removing the film', async ({
  page,
}) => {
  await page.goto('/')
  await saveArrival(page)
  await page.getByRole('button', { name: 'Done', exact: true }).click()
  await page.getByRole('link', { name: 'Collections', exact: true }).click()
  await expect(page).toHaveURL(/\/collections$/)
  await page
    .getByRole('button', { name: 'New collection', exact: true })
    .click()
  const dialog = page.getByRole('dialog')
  await dialog.getByRole('button', { name: 'Create', exact: true }).click()
  await expect(dialog.getByRole('alert')).toHaveText('Enter a collection name.')
  await dialog.getByLabel('New collection name').fill('All saved')
  await dialog.getByRole('button', { name: 'Create', exact: true }).click()
  await expect(dialog.getByRole('alert')).toContainText('reserved')
  await dialog
    .getByLabel('New collection name')
    .fill('  Weekend   favourites  ')
  await dialog.getByRole('button', { name: 'Create', exact: true }).click()
  const rename = page.getByRole('button', { name: 'Rename', exact: true })
  const remove = page.getByRole('button', { name: 'Delete collection', exact: true })
  await expect(rename).toHaveText('')
  await expect(remove).toHaveText('')
  const nameBox = await page.locator('.collection-title-row h2').boundingBox()
  const renameBox = await rename.boundingBox()
  expect(renameBox!.width).toBeGreaterThanOrEqual(44)
  expect(renameBox!.height).toBeGreaterThanOrEqual(44)
  expect(Math.abs(renameBox!.y + renameBox!.height / 2 - nameBox!.y - nameBox!.height / 2)).toBeLessThan(2)
  await rename.click()
  await dialog.getByLabel('Collection name', { exact: true }).fill('Rainy days')
  await dialog.getByRole('button', { name: 'Save name', exact: true }).click()
  await expect(
    page.getByRole('heading', { name: 'Rainy days', exact: true }),
  ).toBeVisible()
  await page
    .getByRole('button', { name: 'Delete collection', exact: true })
    .click()
  await dialog
    .getByRole('button', { name: 'Delete collection', exact: true })
    .click()
  await expect(
    page.getByRole('link', { name: 'Explore Arrival', exact: true }),
  ).toBeVisible()
  await page.reload()
  await expect(
    page.getByRole('link', { name: 'Explore Arrival', exact: true }),
  ).toHaveCount(0)
})

test('temporary saves stay during navigation and disappear on refresh', async ({
  page,
}) => {
  await page.goto('/')
  await saveArrival(page)
  await page.getByRole('button', { name: 'Done', exact: true }).click()
  await expect(
    page.getByRole('link', { name: 'Sign in to keep your saves' }),
  ).toBeVisible()
  await page.getByRole('link', { name: 'Collections', exact: true }).click()
  await expect(page).toHaveURL(/\/collections$/)
  await expect(
    page.getByRole('link', { name: 'Explore Arrival', exact: true }),
  ).toBeVisible()
  expect(
    await page.evaluate(() => localStorage.getItem('frame.demo.collection.v1')),
  ).toBeNull()
  await page.reload()
  await expect(
    page.getByRole('heading', { name: 'Start your film collection' }),
  ).toBeVisible()
  await expect(
    page.getByRole('link', { name: 'Sign in to keep your saves' }),
  ).toHaveCount(0)
})

test('temporary picker supports keyboard and long collection names on mobile', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/movies/329865')
  const trigger = page.getByRole('button', {
    name: 'Save Arrival to collection',
    exact: true,
  })
  await trigger.focus()
  await trigger.press('Enter')
  const dialog = page.getByRole('dialog')
  await expect(
    dialog.getByRole('button', { name: 'Close collection dialog' }),
  ).toBeFocused()
  await dialog
    .getByLabel('New collection name')
    .fill('A very long collection name for films to watch at the weekend')
  await dialog.getByRole('button', { name: 'Create', exact: true }).click()
  expect(await dialog.evaluate((e) => e.scrollWidth <= e.clientWidth)).toBe(
    true,
  )
  await page.keyboard.press('Escape')
  await expect(dialog).toHaveCount(0)
  await expect(
    page.getByRole('button', {
      name: 'Manage collections for Arrival',
      exact: true,
    }),
  ).toBeFocused()
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true)
})

test('new tabs do not inherit temporary saves and retired browser data is ignored', async ({
  page,
  context,
}) => {
  await page.addInitScript(() =>
    localStorage.setItem(
      'frame.demo.collection.v1',
      JSON.stringify({ saved: [329865], watched: [329865] }),
    ),
  )
  await page.goto('/collections')
  await expect(
    page.getByRole('link', { name: 'Explore Arrival', exact: true }),
  ).toHaveCount(0)
  await page.getByRole('link', { name: 'Discover', exact: true }).click()
  await saveArrival(page)
  await page.getByRole('button', { name: 'Done', exact: true }).click()
  const other = await context.newPage()
  await other.goto('/collections')
  await expect(
    other.getByRole('link', { name: 'Explore Arrival', exact: true }),
  ).toHaveCount(0)
  await page.getByRole('link', { name: 'Collections', exact: true }).click()
  await expect(page).toHaveURL(/\/collections$/)
  await expect(
    page.getByRole('link', { name: 'Explore Arrival', exact: true }),
  ).toBeVisible()
  await other.close()
})
