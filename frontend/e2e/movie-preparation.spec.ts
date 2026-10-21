import { expect, memberTest as test } from './fixtures'

for (const mobile of [false, true]) {
  test(`movie page hides draft tooling and places navigation below hero actions (${mobile ? 'mobile' : 'desktop'})`, async ({ page }) => {
    if (mobile) await page.setViewportSize({ width: 375, height: 812 })
    let calls = 0
    await page.route('**/api/movies/*/preparation**', route => { calls++; return route.fulfill({ json: { available: true, job: null } }) })
    await page.goto('/movies/27205')
    await expect(page.getByRole('heading', { name: 'Inception', level: 1 })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Back to discovery' })).toHaveCount(0)
    await expect(page.getByRole('button', { name: /Draft workspace/ })).toHaveCount(0)
    expect(await page.locator('.movie-section-nav').evaluate(nav =>
      Boolean(document.querySelector('.detail-actions')!.compareDocumentPosition(nav) & Node.DOCUMENT_POSITION_FOLLOWING)
      && Boolean(nav.compareDocumentPosition(document.querySelector('#about')!) & Node.DOCUMENT_POSITION_FOLLOWING))).toBe(true)
    await page.getByRole('switch', { name: 'Allow spoilers' }).check()
    await expect(page.getByRole('button', { name: /Draft workspace|Prepare drafts/ })).toHaveCount(0)
    await page.reload()
    await expect(page.getByRole('switch', { name: 'Allow spoilers' })).toBeChecked()
    await expect(page.getByRole('button', { name: /Draft workspace/ })).toHaveCount(0)
    await page.getByRole('switch', { name: 'Allow spoilers' }).uncheck()
    expect(calls).toBe(0)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}
