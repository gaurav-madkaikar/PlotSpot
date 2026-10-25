import { test, expect } from './fixtures'

test('cached results from before the genre field was added still render', async ({
  page,
}) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/e2e/fixtures/search-recovery.html')
  await expect(
    page.getByRole('link', { name: 'Explore Arrival', exact: true }),
  ).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Outdated semantic result' })).toHaveCount(0)
  expect(errors).toEqual([])
})

test('unexpected route errors show recovery actions without technical details', async ({
  page,
}) => {
  await page.goto('/e2e/fixtures/search-recovery.html?broken')
  await expect(page.getByRole('alert')).toContainText(
    'Something interrupted this page.',
  )
  await expect(page.getByRole('button', { name: 'Reload page' })).toBeVisible()
  await expect(page.getByRole('alert')).not.toContainText('Private diagnostic')
  await page.getByRole('link', { name: 'Back to discovery' }).click()
  await expect(page.getByRole('searchbox')).toBeVisible()
})

test('desktop controls share a row, focus stays inside rounded controls, mobile fits', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/')
  const controls = [
    page.getByRole('searchbox'),
    page.getByLabel('Genre', { exact: true }),
    page.getByLabel('Maximum runtime'),
    page.getByLabel('Language', { exact: true }),
  ]
  const boxes = await Promise.all(
    controls.map((control) => control.locator('..').boundingBox()),
  )
  for (const box of boxes)
    expect(Math.abs(box!.y - boxes[0]!.y)).toBeLessThan(2)
  for (const control of controls) {
    await control.focus()
    const style = await control.evaluate((element) => {
      const parent = getComputedStyle(element.parentElement!)
      return {
        radius: parent.borderRadius,
        outline: parent.outlineStyle,
        shadow: parent.boxShadow,
      }
    })
    expect(style.radius).toBe('12px')
    expect(style.outline).toBe('none')
    expect(style.shadow).toContain('inset')
  }
  await page.setViewportSize({ width: 390, height: 844 })
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy()
})
