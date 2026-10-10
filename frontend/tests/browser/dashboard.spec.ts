import { mkdirSync } from 'node:fs'
import path from 'node:path'
import { expect, test, type Page } from '@playwright/test'

const evidenceDirectory = path.resolve(process.cwd(), '../docs/qa/screenshots/issue-24-gate-2')
mkdirSync(evidenceDirectory, { recursive: true })

type PageSignals = { errors: string[]; apiRequests: string[] }

function observePage(page: Page): PageSignals {
  const signals: PageSignals = { errors: [], apiRequests: [] }
  page.on('pageerror', (error) => signals.errors.push(error.message))
  page.on('console', (message) => {
    if (message.type() === 'error') signals.errors.push(message.text())
  })
  page.on('request', (request) => {
    if (new URL(request.url()).pathname.startsWith('/autostock/api/')) signals.apiRequests.push(request.url())
  })
  return signals
}

function expectClean(signals: PageSignals) {
  expect(signals.apiRequests, 'Gate 2 must use local fixtures and send zero Odoo API requests').toEqual([])
  expect(signals.errors, 'the browser must have no page or console errors').toEqual([])
}

async function expectNoHorizontalOverflow(page: Page, width: number) {
  const dimensions = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }))
  expect(dimensions.viewport).toBe(width)
  expect(dimensions.document, `${width}px document overflow`).toBeLessThanOrEqual(width)
  expect(dimensions.body, `${width}px body overflow`).toBeLessThanOrEqual(width)
}

test('dashboard navigation and content fit desktop, tablet, and mobile widths', async ({ page }) => {
  const signals = observePage(page)
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Dashboard', level: 1 })).toBeVisible()

  for (const viewport of [
    { width: 1440, height: 1000 },
    { width: 1024, height: 800 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport)
    await expectNoHorizontalOverflow(page, viewport.width)
    await expect(page.locator('.kpi-card')).toHaveCount(5)
    await expect(page.locator('.insight-card')).toHaveCount(3)
    await expect(page.getByRole('heading', { name: 'Demand forecast' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Inventory Health' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Restock recommendations' })).toBeVisible()
    const plotWidth = await page.locator('[data-testid="forecast-plot"] svg').evaluate((svg) => svg.getBoundingClientRect().width)
    expect(plotWidth, `${viewport.width}px forecast plot width`).toBeGreaterThan(200)
  }
  expectClean(signals)
})

test('Ctrl/Cmd+K searches fixture product metadata and opens a keyboard-selected quick view', async ({ page }) => {
  const signals = observePage(page)
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Search parts, SKUs, vehicles, or suppliers' })).toBeVisible()
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))))
  await page.keyboard.press('Control+k')

  const dialog = page.getByRole('dialog', { name: 'Search AutoStock' })
  await expect(dialog).toBeVisible()
  const input = dialog.getByRole('combobox', { name: 'Search parts, SKUs, vehicles, and suppliers' })
  await expect(input).toBeFocused()
  await input.fill('Northline Auto Supply')
  const result = dialog.getByRole('option', { name: /Brake Pads \(Front\).*BP-001/ })
  await expect(result).toBeVisible()
  await page.screenshot({ path: path.join(evidenceDirectory, 'search-open-1440.png'), fullPage: false, animations: 'disabled' })

  await input.press('ArrowDown')
  await expect(result).toHaveAttribute('aria-selected', 'true')
  await input.press('Enter')
  const quickView = page.getByRole('dialog', { name: /Brake Pads \(Front\)/ })
  await expect(quickView).toBeVisible()
  await expect(quickView.getByText('SKU BP-001')).toBeVisible()
  await expect(quickView.getByRole('heading', { name: 'Supplier' })).toBeVisible()
  await expect(quickView).toContainText('Northline Auto Supply')

  await page.keyboard.press('Escape')
  await page.keyboard.press('Meta+k')
  await expect(dialog).toBeVisible()
  await input.fill('Toyota Corolla')
  await expect(dialog.getByRole('option')).toHaveCount(3)
  expectClean(signals)
})


test('search dialog stays fully inside the viewport even after page scrolling', async ({ page }) => {
  const signals = observePage(page)
  await page.setViewportSize({ width: 1440, height: 800 })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Dashboard', level: 1 })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Search parts, SKUs, vehicles, or suppliers' })).toBeVisible()
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
  await page.keyboard.press('Control+k')
  const dialog = page.getByRole('dialog', { name: 'Search AutoStock' })
  await expect(dialog).toBeVisible()
  const box = await dialog.boundingBox()
  if (!box) throw new Error('Search dialog has no layout box')
  expect(box.y).toBeGreaterThanOrEqual(8)
  expect(box.y + box.height).toBeLessThanOrEqual(792)
  expectClean(signals)
})

test('collapsed sidebar keeps the brand and expand control separate and discoverable', async ({ page }) => {
  const signals = observePage(page)
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')
  await page.getByRole('button', { name: /Collapse navigation/ }).click()
  const brand = page.locator('.sidebar-rail .brand-symbol')
  const toggle = page.getByRole('button', { name: /Expand navigation/ })
  const brandBox = await brand.boundingBox()
  const toggleBox = await toggle.boundingBox()
  if (!brandBox || !toggleBox) throw new Error('Collapsed navigation controls are not laid out')
  const overlap = !(toggleBox.x >= brandBox.x + brandBox.width || toggleBox.x + toggleBox.width <= brandBox.x || toggleBox.y >= brandBox.y + brandBox.height || toggleBox.y + toggleBox.height <= brandBox.y)
  expect(overlap).toBe(false)
  await expect(page.getByRole('button', { name: 'Dashboard' })).toHaveAttribute('title', 'Dashboard')
  expectClean(signals)
})

test('forecast product and horizon controls update the chart and expose hover and keyboard details', async ({ page }) => {
  const signals = observePage(page)
  await page.setViewportSize({ width: 1024, height: 820 })
  await page.goto('/')

  await page.getByLabel('Forecast product').selectOption('OF-203')
  await page.getByLabel('Forecast horizon').selectOption('7')
  await expect(page.locator('[data-testid="forecast-selection-status"]')).toContainText('Oil Filter')
  await expect(page.locator('[data-testid="forecast-selection-status"]')).toContainText('next 7 days')
  const chart = page.getByRole('group', { name: /Oil Filter.*expected demand over 7 days/i })
  await expect(chart).toBeVisible()

  const plot = page.getByTestId('forecast-plot')
  const bounds = await plot.boundingBox()
  if (!bounds) throw new Error('Forecast plot is not laid out')
  await page.mouse.move(bounds.x + bounds.width * 0.79, bounds.y + bounds.height * 0.42)
  await expect(page.locator('.chart-tooltip')).toHaveAttribute('data-visible', 'true')
  await expect(page.locator('.chart-tooltip')).toContainText('Expected demand')
  await expect(page.locator('.chart-tooltip')).toContainText('Typical range')
  await page.screenshot({ path: path.join(evidenceDirectory, 'forecast-interaction-1024.png'), fullPage: false, animations: 'disabled' })

  await plot.focus()
  await page.keyboard.press('ArrowRight')
  await expect(page.locator('.chart-tooltip')).toHaveAttribute('data-visible', 'true')
  await page.getByLabel('Forecast horizon').selectOption('60')
  await expect(page.locator('[data-testid="forecast-selection-status"]')).toContainText('next 60 days')
  expectClean(signals)
})

test('restock risk and category filters work and details explain the sample recommendation', async ({ page }) => {
  const signals = observePage(page)
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/')

  await page.getByRole('button', { name: 'Risk filter: all priorities' }).click()
  await page.getByRole('menuitemradio', { name: 'High priority' }).click()
  await expect(page.locator('.reorder-table tbody tr')).toHaveCount(3)
  await expect(page.getByRole('button', { name: 'Risk filter: High priority' })).toBeVisible()

  await page.getByRole('button', { name: 'Category: All categories' }).click()
  await page.getByRole('menuitem', { name: 'Brakes' }).click()
  await expect(page.locator('.reorder-table tbody tr')).toHaveCount(1)
  await expect(page.locator('.reorder-table tbody')).toContainText('BP-001')

  await page.getByRole('button', { name: /Open restock details for Brake Pads \(Front\)/ }).click()
  const drawer = page.getByRole('dialog', { name: /Brake Pads \(Front\)/ })
  await expect(drawer).toBeVisible()
  await expect(drawer.getByRole('heading', { name: 'Why this recommendation?' })).toBeVisible()
  await expect(drawer.getByText('Northline Auto Supply')).toBeVisible()
  await drawer.getByText('How calculated?').click()
  await expect(drawer.getByText('The suggested quantity is a typed development fixture value.')).toBeVisible()
  await expect(drawer.getByRole('button', { name: /Create PO/ })).toHaveCount(0)
  await page.screenshot({ path: path.join(evidenceDirectory, 'restock-detail-drawer-1440.png'), fullPage: false, animations: 'disabled' })
  expectClean(signals)
})

test('mobile navigation closes after a selection and mobile restock filters remain reachable', async ({ page }) => {
  const signals = observePage(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await page.getByRole('button', { name: 'Open navigation menu' }).click()
  const navSheet = page.getByRole('dialog', { name: 'AutoStock navigation' })
  await expect(navSheet).toBeVisible()
  await page.screenshot({ path: path.join(evidenceDirectory, 'mobile-navigation-390.png'), fullPage: false, animations: 'disabled' })
  await navSheet.getByRole('button', { name: 'Forecasts' }).click()
  await expect(navSheet).toBeHidden()
  await expect(page.getByRole('heading', { name: 'Demand forecast' })).toBeVisible()
  await expectNoHorizontalOverflow(page, 390)

  await page.getByRole('button', { name: 'More restock list options' }).click()
  await page.getByRole('menuitem', { name: 'Filters', exact: true }).click()
  await expect(page.locator('.reorder-table tbody tr')).toHaveCount(2)
  await expect(page.locator('.reorder-table tbody')).toContainText('OF-203')
  await expect(page.locator('.reorder-table tbody')).toContainText('AF-331')
  await expect(page.locator('.reorder-table tbody')).not.toContainText('BP-001')
  await expectNoHorizontalOverflow(page, 390)
  expectClean(signals)
})

test('dashboard actions show useful preview details and date range stays connected to the forecast', async ({ page }) => {
  const signals = observePage(page)
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/')

  await page.getByRole('button', { name: /Date range/ }).click()
  await page.getByRole('menuitem', { name: 'Last 60 days' }).click()
  await expect(page.locator('.forecast-heading p')).toContainText('60 days')

  await page.getByRole('button', { name: 'See details' }).click()
  const healthDrawer = page.getByRole('dialog', { name: 'Inventory health' })
  await expect(healthDrawer).toContainText('73%')
  await expect(healthDrawer).toContainText('Illustrative fixture totals')
  await page.keyboard.press('Escape')

  await page.getByRole('button', { name: 'See all insights' }).click()
  await expect(page.getByRole('dialog', { name: 'Insights for this sample' })).toContainText('No order or inventory change')
  await page.keyboard.press('Escape')

  await page.getByRole('button', { name: 'Review Parts' }).click()
  await expect(page.getByRole('button', { name: 'Risk filter: High priority' })).toBeVisible()
  await page.getByRole('button', { name: 'View Reorder List' }).click()
  await expect(page.locator('.reorder-table tbody tr')).toHaveCount(5)
  await page.getByLabel('Forecast product').selectOption('BT-912')
  await page.getByRole('button', { name: 'Explore Forecast' }).click()
  await expect(page.locator('[data-testid="forecast-selection-status"]')).toContainText('Brake Pads')

  await page.getByRole('button', { name: 'Notifications, 3 sample updates' }).click()
  await expect(page.getByRole('menu').getByText('Recent updates')).toBeVisible()
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: 'Profile menu for Alex Morgan' }).click()
  await expect(page.getByRole('menu')).toContainText('Local preview account')
  await page.keyboard.press('Escape')

  await page.getByRole('button', { name: /Collapse navigation/ }).click()
  await expect(page.locator('.sidebar-rail')).toHaveClass(/is-collapsed/)
  await page.getByRole('button', { name: /Expand navigation/ }).click()
  await expect(page.locator('.sidebar-rail')).not.toHaveClass(/is-collapsed/)
  expectClean(signals)
})

test('loading, empty, and error fixture states have clear recovery actions', async ({ page }) => {
  const signals = observePage(page)
  await page.goto('/?fixtureState=loading')
  await expect(page.getByRole('status', { name: 'Loading sample forecast' })).toBeVisible()
  await expect(page.locator('.table-loading-state')).toBeVisible()

  await page.goto('/?fixtureState=empty')
  await expect(page.getByText('No forecast to show yet')).toBeVisible()
  await expect(page.getByText('No recommendations to show yet')).toBeVisible()
  await page.getByRole('button', { name: 'Show sample forecast' }).click()
  await expect(page.locator('.reorder-table tbody tr')).toHaveCount(5)
  await expect(page.locator('[data-testid="forecast-plot"]')).toBeVisible()

  await page.goto('/?fixtureState=error')
  await expect(page.getByRole('alert').getByText('This sample forecast is unavailable')).toBeVisible()
  await page.locator('#forecast-panel').getByRole('button', { name: 'Try again' }).click()
  await expect(page.locator('[data-testid="forecast-plot"]')).toBeVisible()
  expectClean(signals)
})

test('reduced-motion preference suppresses interface transitions and fixture animation', async ({ page }) => {
  const signals = observePage(page)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/?fixtureState=loading')
  await expect(page.locator('.insight-action')).toHaveCount(3)
  await expect(page.locator('.loading-sparkline')).toBeVisible()
  const motion = await page.evaluate(() => ({
    reduced: matchMedia('(prefers-reduced-motion: reduce)').matches,
    buttonTransition: getComputedStyle(document.querySelector('.insight-action')!).transitionDuration,
    shimmerAnimation: getComputedStyle(document.querySelector('.loading-sparkline')!).animationDuration,
  }))
  expect(motion.reduced).toBe(true)
  expect(Number.parseFloat(motion.buttonTransition)).toBeLessThanOrEqual(0.001)
  expect(Number.parseFloat(motion.shimmerAnimation)).toBeLessThanOrEqual(0.001)
  expectClean(signals)
})
