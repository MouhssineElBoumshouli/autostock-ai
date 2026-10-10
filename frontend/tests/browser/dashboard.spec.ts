import { expect, test, type Page, type Route } from '@playwright/test'

type ApiMode = 'live-contract' | 'empty' | 'loading' | 'error'
type PageSignals = { errors: string[]; runtimeErrors: string[]; apiRequests: string[]; apiFailures: string[] }

const apiModes = new WeakMap<Page, ApiMode>()
const pendingForecastReleases = new WeakMap<Page, () => void>()
const company = (id: number) => ({
  id,
  name: id === 1 ? 'Atlas Auto Distribution' : 'Atlas East Parts',
  logo_url: '',
  currency: { code: 'MAD', symbol: 'DH', decimal_places: 2 },
  demo_environment: true,
  demo_environment_note: 'Demonstration company.',
})

const parts = [
  { id: 101, template_id: 101, name: 'Brake Pads (Front)', sku: 'BP-001', reference: 'AT-BP-101', category: 'Brakes', supplier_names: ['Northline Auto Supply'] },
  { id: 203, template_id: 203, name: 'Oil Filter', sku: 'OF-203', reference: 'AT-OF-203', category: 'Filters', supplier_names: ['Northline Auto Supply'] },
  { id: 331, template_id: 331, name: 'Air Filter', sku: 'AF-331', reference: 'AT-AF-331', category: 'Filters', supplier_names: ['Atlas Components'] },
  { id: 912, template_id: 912, name: 'Battery', sku: 'BT-912', reference: 'AT-BT-912', category: 'Electrical', supplier_names: ['Atlas Components'] },
  { id: 404, template_id: 404, name: 'Ignition Coil', sku: 'IG-404', reference: 'AT-IG-404', category: 'Ignition', supplier_names: [] },
]

function stockItem(index: number) {
  const part = parts[index]
  const high = [0, 3, 4].includes(index)
  const isOut = index === 0
  const current = isOut ? 0 : index === 3 ? 1 : index === 1 ? 3 : index === 2 ? 2 : 2
  const supplier = part.supplier_names.length ? part.supplier_names[0] : false
  return {
    key: `${part.id}-10`, product_id: part.id, template_id: part.template_id, name: part.name, sku: part.sku,
    reference: part.reference, category: part.category, warehouse_id: 10, warehouse: 'Main Warehouse',
    status: isOut ? 'out' : high ? 'shortage' : 'low', status_label: isOut ? 'Out of stock' : high ? 'Shortage' : 'Low stock',
    current_qty: current, free_qty: current, reserved_qty: 0, incoming_qty: 0, outgoing_qty: 0,
    projected_qty: current, projected_after_demand: current, forecast_demand: false, forecast_used: false,
    forecast_reason: 'No reviewed forecast is available for this part.', forecast_horizon_days: false,
    forecast_review_status: false, uom: 'Units', recommended_qty: isOut ? 12 : high ? 8 : 6,
    reorder_needed: true, supplier_name: supplier,
    supplier: supplier ? { id: index + 30, name: supplier, lead_days: 8, minimum_qty: 1, minimum_uom: 'Units', price_tier_min_qty: 0, price_tier_uom: 'Units', price: 100, currency: 'MAD', company_specific: true } : false,
    supplier_access_note: false,
    reason: isOut ? 'No stock is on hand at this warehouse.' : 'Stock is below the configured reorder trigger.',
    basis_note: 'Quantity comes from current Odoo stock and the configured reorder policy.',
    lead_time_days: 8, lead_time_source: 'supplier', lead_time_label: 'Supplier lead time',
    minimum_threshold: 5, target_stock: 12, policy_source: 'reorder_rule', policy_source_label: 'Odoo reorder rule',
    policy_issue: false, calculation_basis: 'Current stock and Odoo reorder policy.',
  }
}

const riskItems = parts.map((_, index) => stockItem(index))
const forecastOptions = parts.slice(0, 3).map((part) => ({
  key: `${part.id}-10`, product_id: part.id, name: part.name, sku: part.sku, warehouse_id: 10, warehouse: 'Main Warehouse',
}))

function dayOffset(offset: number) {
  const date = new Date()
  date.setDate(date.getDate() + offset)
  return date.toISOString().slice(0, 10)
}

function forecast(productId: number, horizon: number) {
  const part = parts.find((item) => item.id === productId) ?? parts[0]
  const daily = Math.max(1, Math.round(horizon / 10))
  return {
    id: productId * 10 + horizon, product_name: part.name, sku: part.sku, warehouse_name: 'Main Warehouse',
    horizon_days: horizon, uom: 'Units', source_type: 'delivery_history', source_label: 'completed customer deliveries',
    review_status: 'reviewed', evaluation_status: 'evaluated', history_start: dayOffset(-7), history_end: dayOffset(-1),
    history: [-7, -5, -3, -1].map((offset, index) => ({ date: dayOffset(offset), units: daily + index })),
    predictions: [1, 2, 3, 4].map((offset, index) => ({
      date: dayOffset(offset * Math.max(1, Math.floor(horizon / 4))), units: daily + index,
      lower: Math.max(0, daily + index - 1), upper: daily + index + 2,
    })),
    limitations: 'Planning context based on completed deliveries; future demand may differ.',
  }
}

function dashboardData(companyId: number, empty = false) {
  return {
    schema_version: 1,
    company: company(companyId),
    snapshot_at: new Date().toISOString(),
    kpis: {
      tracked_products: empty ? 0 : 64, in_stock: empty ? 0 : 58, low_stock: empty ? 0 : 6,
      out_of_stock: 0, reviewed_forecasts: empty ? 0 : 4, reviewed_forecasts_available: true,
    },
    inventory_health: {
      total_tracked: empty ? 0 : 64, sampled_products: empty ? 0 : 64, complete: true,
      categories: [
        { key: 'healthy', label: 'In stock', count: empty ? 0 : 58, percent: empty ? 0 : 91 },
        { key: 'low', label: 'Low stock', count: empty ? 0 : 6, percent: empty ? 0 : 9 },
        { key: 'out', label: 'Out of stock', count: 0, percent: 0 },
      ],
    },
    empty,
  }
}

function restockData(companyId: number, empty = false) {
  return {
    schema_version: 1, company: company(companyId), warehouse_id: false,
    warehouses: [{ id: 10, name: 'Main Warehouse' }], as_of: new Date().toISOString(), read_only: true,
    summary: { priority_locations: empty ? 0 : 5, reorder_suggestions: empty ? 0 : 5, complete: true },
    items: empty ? [] : riskItems,
    insights: [
      { id: 'reorder-suggestions', title: 'Reorder suggestions', description: empty ? 'No part locations have a suggested order ready for review.' : '5 part locations have a suggested order ready for review.', icon: 'reorder', action: 'view-reorder', action_label: 'View top 5' },
      { id: 'stock-review', title: 'Part locations to review', description: empty ? 'No part locations need review.' : '5 part locations need review because stock is low or empty, or their reorder rules need attention.', icon: 'trend', action: 'review-parts', action_label: 'Review parts' },
      { id: 'out-of-stock', title: 'Warehouse stockouts', description: empty ? 'No part locations currently have zero stock.' : '1 part location currently has zero stock. This part may still have stock in another warehouse.', icon: 'vehicle', action: 'view-reorder', action_label: 'View top 5' },
    ],
    coverage: { complete: true, scanned_locations: empty ? 0 : 64, candidate_locations: empty ? 0 : 64, scan_limit: 500, flags: { warehouse_scope_limited: false, supplier_filter_limited: false, forecast_lookup_limited: false } },
  }
}

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(payload) })
}

async function installOdooContractStub(page: Page) {
  apiModes.set(page, 'live-contract')
  await page.route('**/autostock/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname
    const companyId = Number(url.searchParams.get('company_id') ?? 1)
    const mode = apiModes.get(page) ?? 'live-contract'

    if (path.endsWith('/session')) {
      const currentCompany = company(companyId)
      return fulfillJson(route, {
        schema_version: 1, authenticated: true,
        user: { id: 5, name: 'Alex Morgan', locale: 'en_US', timezone: 'UTC', permissions: { inventory: true, sales: true, inventory_manager: true } },
        current_company: currentCompany, allowed_companies: [company(1), company(2)],
      })
    }
    if (path.endsWith('/dashboard')) return fulfillJson(route, dashboardData(companyId, mode === 'empty'))
    if (path.endsWith('/restock-preview')) return fulfillJson(route, restockData(companyId, mode === 'empty'))
    if (path.endsWith('/forecast-preview')) {
      if (mode === 'loading') await new Promise<void>((resolve) => pendingForecastReleases.set(page, resolve))
      if (mode === 'error') return fulfillJson(route, { error: { code: 'temporarily_unavailable', message: 'Forecast service temporarily unavailable.' } }, 503)
      if (mode === 'empty') {
        return fulfillJson(route, {
          schema_version: 1, company: company(companyId), status: 'unavailable',
          reason_code: 'no_evaluated_forecast', message: 'No completed, evaluated forecast is available for this company and horizon.',
          options: [], options_limited: false, forecast: false,
        })
      }
      const horizon = Number(url.searchParams.get('horizon_days') ?? 30)
      const productId = Number(url.searchParams.get('product_id') ?? parts[0].id)
      const selectedForecast = forecast(productId, horizon)
      return fulfillJson(route, {
        schema_version: 1, company: company(companyId), status: 'available', reason_code: false, message: false,
        options: forecastOptions, options_limited: false, forecast: selectedForecast,
      })
    }
    if (path.endsWith('/search/products')) {
      const query = (url.searchParams.get('q') ?? '').toLowerCase()
      const results = query.includes('toyota')
        ? parts.slice(0, 3)
        : parts.filter((part) => [part.name, part.sku, part.reference, ...part.supplier_names].join(' ').toLowerCase().includes(query))
      return fulfillJson(route, { schema_version: 1, query: url.searchParams.get('q') ?? '', limited: false, results })
    }
    const productMatch = path.match(/\/products\/(\d+)\/quick-view$/)
    if (productMatch) {
      const part = parts.find((item) => item.id === Number(productMatch[1])) ?? parts[0]
      const position = riskItems.find((item) => item.product_id === part.id) ?? riskItems[0]
      return fulfillJson(route, {
        schema_version: 1, company: company(companyId), read_only: true,
        product: { id: part.id, template_id: part.template_id, name: part.name, sku: part.sku, reference: part.reference, category: part.category, tracked: true },
        positions: [position], coverage: { complete: true, candidate_locations: 1, scanned_locations: 1 },
      })
    }
    return fulfillJson(route, { error: { code: 'not_found', message: 'Unknown test API route.' } }, 404)
  })
}

function observePage(page: Page): PageSignals {
  const signals: PageSignals = { errors: [], runtimeErrors: [], apiRequests: [], apiFailures: [] }
  page.on('pageerror', (error) => { signals.errors.push(error.message); signals.runtimeErrors.push(error.message) })
  page.on('console', (message) => {
    if (message.type() === 'error') signals.errors.push(message.text())
  })
  page.on('request', (request) => {
    if (new URL(request.url()).pathname.startsWith('/autostock/api/v1/')) signals.apiRequests.push(request.url())
  })
  page.on('response', (response) => {
    if (new URL(response.url()).pathname.startsWith('/autostock/api/v1/') && response.status() >= 400) {
      signals.apiFailures.push(`${new URL(response.url()).pathname}: ${response.status()}`)
    }
  })
  return signals
}

function expectClean(signals: PageSignals) {
  const paths = new Set(signals.apiRequests.map((request) => new URL(request).pathname))
  expect(paths).toContain('/autostock/api/v1/session')
  expect(paths).toContain('/autostock/api/v1/dashboard')
  expect(paths).toContain('/autostock/api/v1/dashboard/restock-preview')
  expect(paths).toContain('/autostock/api/v1/dashboard/forecast-preview')
  expect(signals.apiFailures, 'successful API contract journeys must not produce API errors').toEqual([])
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

test.beforeEach(async ({ page }) => installOdooContractStub(page))

test('dashboard navigation and live API contract fit desktop, tablet, and mobile widths', async ({ page }) => {
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
    const clippedKpiLabels = await page.locator('.kpi-label').evaluateAll((labels) => labels
      .filter((label) => label.scrollWidth > label.clientWidth + 1)
      .map((label) => label.textContent?.trim()))
    expect(clippedKpiLabels, `${viewport.width}px KPI labels should stay readable`).toEqual([])
    await expect(page.locator('.insight-card')).toHaveCount(3)
    await expect(page.getByRole('heading', { name: 'Demand forecast' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Inventory Health' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Restock recommendations' })).toBeVisible()
    const plotWidth = await page.locator('[data-testid="forecast-plot"] svg').evaluate((svg) => svg.getBoundingClientRect().width)
    expect(plotWidth, `${viewport.width}px forecast plot width`).toBeGreaterThan(200)
  }
  expectClean(signals)
})

test('Ctrl/Cmd+K searches Odoo contract results and opens a keyboard-selected product quick view', async ({ page }) => {
  const signals = observePage(page)
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Search parts, SKUs, suppliers, or references' })).toBeVisible()
  await page.keyboard.press('Control+k')

  const dialog = page.getByRole('dialog', { name: 'Search AutoStock' })
  await expect(dialog).toBeVisible()
  const input = dialog.getByRole('combobox', { name: 'Search parts, SKUs, suppliers, and references' })
  await expect(input).toBeFocused()
  await input.fill('Northline Auto Supply')
  const firstResult = dialog.getByRole('option', { name: /Brake Pads \(Front\).*BP-001/ })
  const secondResult = dialog.getByRole('option', { name: /Oil Filter.*OF-203/ })
  await expect(firstResult).toBeVisible()
  await expect(secondResult).toBeVisible()

  await expect(input).toBeFocused()
  await expect(firstResult).toHaveAttribute('aria-selected', 'true')
  await page.keyboard.press('ArrowDown')
  await expect(secondResult).toHaveAttribute('aria-selected', 'true')
  await page.keyboard.press('Enter')
  const quickView = page.getByRole('dialog', { name: /Oil Filter/ })
  await expect(quickView).toBeVisible()
  await expect(quickView.getByText('SKU OF-203')).toBeVisible()
  await expect(quickView.getByRole('heading', { name: 'Supplier and delivery' })).toBeVisible()
  await expect(quickView).toContainText('Northline Auto Supply')
  await expect(page.getByRole('button', { name: /Create PO/ })).toHaveCount(0)

  await page.keyboard.press('Escape')
  await page.keyboard.press('Meta+k')
  await expect(dialog).toBeVisible()
  await input.fill('Toyota Corolla')
  await expect(dialog.getByRole('option')).toHaveCount(3)
  const options = dialog.getByRole('option')
  await expect(options.nth(0)).toHaveAttribute('aria-selected', 'true')
  await input.press('ArrowDown')
  await expect(options.nth(1)).toHaveAttribute('aria-selected', 'true')
  await input.press('Enter')
  await expect(page.getByRole('dialog', { name: /Oil Filter/ })).toBeVisible()
  expectClean(signals)
})

test('search dialog stays inside the viewport after page scrolling', async ({ page }) => {
  const signals = observePage(page)
  await page.setViewportSize({ width: 1440, height: 800 })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Dashboard', level: 1 })).toBeVisible()
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

test('collapsed sidebar keeps its brand and expand control separate', async ({ page }) => {
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
  await expect(page.getByRole('button', { name: 'Dashboard', exact: true })).toHaveAttribute('title', 'Dashboard')
  expectClean(signals)
})

test('forecast product and horizon controls update the company forecast and chart details', async ({ page }) => {
  const signals = observePage(page)
  await page.setViewportSize({ width: 1024, height: 820 })
  await page.goto('/')

  await page.getByLabel('Forecast product').selectOption('203-10')
  await expect(page.locator('[data-testid="forecast-selection-status"]')).toContainText('Oil Filter')
  const firstChart = page.getByRole('group', { name: /Oil Filter.*expected demand over 30 days/i })
  await expect(firstChart).toBeVisible()
  await page.getByLabel('Forecast horizon').selectOption('7')
  await page.getByLabel('Forecast product').selectOption('203-10')
  await expect(page.locator('[data-testid="forecast-selection-status"]')).toContainText('next 7 days')
  const chart = page.getByRole('group', { name: /Oil Filter.*expected demand over 7 days/i })
  await expect(chart).toBeVisible()

  const plot = page.getByTestId('forecast-plot')
  const bounds = await plot.boundingBox()
  if (!bounds) throw new Error('Forecast plot is not laid out')
  await page.mouse.move(bounds.x + bounds.width * 0.79, bounds.y + bounds.height * 0.42)
  await expect(page.locator('.chart-tooltip')).toHaveAttribute('data-visible', 'true')
  await expect(page.locator('.chart-tooltip')).toContainText('Expected demand')
  await expect(page.locator('.chart-tooltip')).toContainText('Planning range')

  await plot.focus()
  await page.keyboard.press('ArrowRight')
  await expect(page.locator('.chart-tooltip')).toHaveAttribute('data-visible', 'true')
  await page.getByLabel('Forecast horizon').selectOption('60')
  await page.getByLabel('Forecast product').selectOption('203-10')
  await expect(page.locator('[data-testid="forecast-selection-status"]')).toContainText('next 60 days')
  expect(signals.apiRequests.some((request) => new URL(request).searchParams.get('horizon_days') === '7')).toBe(true)
  expect(signals.apiRequests.some((request) => new URL(request).searchParams.get('horizon_days') === '60')).toBe(true)
  expectClean(signals)
})

test('restock filters and details explain actual calculation fields while remaining read-only', async ({ page }) => {
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
  await expect(drawer).toContainText('Demand before delivery')
  await expect(drawer).toContainText('No forecast')
  await expect(drawer).toContainText('Northline Auto Supply')
  await drawer.getByText('How calculated?').click()
  await expect(drawer).toContainText('Quantity comes from current Odoo stock and the configured reorder policy.')
  await expect(drawer.getByRole('button', { name: /Create PO/ })).toHaveCount(0)
  expectClean(signals)
})

test('business copy distinguishes company stock from warehouse stockouts and shows Reports as unavailable', async ({ page }) => {
  const signals = observePage(page)
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/')

  const companyOutOfStock = page.locator('.kpi-card').filter({ hasText: 'Out of Stock' })
  await expect(companyOutOfStock).toContainText('No stock across the company')
  const warehouseStockouts = page.locator('.insight-card').filter({ has: page.getByRole('heading', { name: 'Warehouse stockouts' }) })
  await expect(warehouseStockouts).toContainText('1 part location currently has zero stock.')
  await expect(warehouseStockouts).toContainText('This part may still have stock in another warehouse.')

  const reorderPanel = page.locator('#reorder-panel')
  await expect(reorderPanel.getByRole('columnheader', { name: 'Demand before delivery' })).toBeVisible()
  await expect(reorderPanel.getByRole('columnheader', { name: 'Based on' })).toBeVisible()
  await expect(reorderPanel.locator('tbody tr').first()).toContainText('No forecast')
  await expect(reorderPanel.locator('tbody tr').first()).toContainText('Stock + reorder rule')

  const report = page.locator('.report-control')
  await expect(report).toBeDisabled()
  await expect(report).toHaveAttribute('title', 'Reports are not available yet')
  for (const viewport of [{ width: 1440, height: 1000 }, { width: 1024, height: 820 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport)
    await expectNoHorizontalOverflow(page, viewport.width)
    const style = await report.evaluate((button) => {
      const computed = getComputedStyle(button)
      return {
        backgroundColor: computed.backgroundColor,
        backgroundImage: computed.backgroundImage,
        boxShadow: computed.boxShadow,
        color: computed.color,
        cursor: computed.cursor,
        opacity: computed.opacity,
      }
    })
    expect(style.backgroundColor).toBe('rgb(239, 240, 245)')
    expect(style.backgroundImage).toBe('none')
    expect(style.boxShadow).toBe('none')
    expect(style.color).not.toBe('rgb(255, 255, 255)')
    expect(style.cursor).toBe('not-allowed')
    expect(style.opacity).toBe('1')
  }
  expectClean(signals)
})

test('mobile navigation closes after a selection and product category filtering stays reachable', async ({ page }) => {
  const signals = observePage(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await page.getByRole('button', { name: 'Open navigation menu' }).click()
  const navSheet = page.getByRole('dialog', { name: 'AutoStock navigation' })
  await expect(navSheet).toBeVisible()
  await navSheet.getByRole('button', { name: 'Forecasts' }).click()
  await expect(navSheet).toBeHidden()
  await expect(page.getByRole('heading', { name: 'Demand forecast' })).toBeVisible()
  await expectNoHorizontalOverflow(page, 390)
  const mobileFactsAreReadable = await page.locator('.mobile-detail > span').evaluateAll((spans) => spans.every((span) => {
    const label = span.querySelector('small')?.getBoundingClientRect()
    const value = span.querySelector('strong')?.getBoundingClientRect()
    return !label || !value || label.right <= value.left + 1
  }))
  expect(mobileFactsAreReadable).toBe(true)

  await page.getByRole('button', { name: 'More restock list options' }).click()
  await page.getByRole('menuitem', { name: 'Filters', exact: true }).click()
  await expect(page.locator('.reorder-table tbody tr')).toHaveCount(2)
  await expect(page.locator('.reorder-table tbody')).toContainText('OF-203')
  await expect(page.locator('.reorder-table tbody')).toContainText('AF-331')
  await expect(page.locator('.reorder-table tbody')).not.toContainText('BP-001')
  await expectNoHorizontalOverflow(page, 390)
  expectClean(signals)
})

test('date range, inventory health, insight actions, and company switch use the API scope', async ({ page }) => {
  const signals = observePage(page)
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/')

  await page.getByRole('button', { name: /Forecast period/ }).click()
  await page.getByRole('menuitem', { name: 'Next 60 days' }).click()
  await expect(page.locator('.forecast-heading p')).toContainText('60 days')

  await page.getByRole('button', { name: 'See details' }).click()
  const healthDrawer = page.getByRole('dialog', { name: 'Inventory health' })
  await expect(healthDrawer).toContainText('91%')
  await expect(healthDrawer).toContainText('All 64 tracked parts are included.')
  await page.keyboard.press('Escape')

  await page.getByRole('button', { name: 'See all insights' }).click()
  const insights = page.getByRole('dialog', { name: 'Current stock insights' })
  await expect(insights).toContainText('5 part locations have a suggested order ready for review.')
  await expect(insights).toContainText('This part may still have stock in another warehouse.')
  await page.keyboard.press('Escape')

  await page.locator('#reorder-panel').getByRole('button', { name: 'View top 5' }).click()
  await expect(page.getByRole('dialog', { name: 'Top restock recommendations' })).toContainText('Brake Pads (Front)')
  await page.keyboard.press('Escape')

  await page.getByRole('button', { name: 'Profile menu for Alex Morgan' }).click()
  await page.getByRole('menuitemradio', { name: 'Atlas East Parts' }).click()
  await expect(page.getByRole('heading', { name: 'Dashboard', level: 1 }).locator('..')).toContainText('Atlas East Parts')
  expect(signals.apiRequests.some((request) => new URL(request).searchParams.get('company_id') === '2')).toBe(true)
  expectClean(signals)
})

test('loading, empty, and recoverable error responses have clear user states', async ({ page }) => {
  const signals = observePage(page)
  apiModes.set(page, 'loading')
  await page.goto('/')
  await expect(page.getByRole('status', { name: 'Loading demand forecast' })).toBeVisible()
  await expect(page.locator('.table-loading-state')).toHaveCount(0)
  pendingForecastReleases.get(page)?.()
  await expect(page.getByTestId('forecast-plot')).toBeVisible()

  apiModes.set(page, 'empty')
  await page.reload()
  await expect(page.getByText('No forecast to show yet')).toBeVisible()
  await expect(page.getByText('No part locations need review', { exact: true })).toBeVisible()

  apiModes.set(page, 'error')
  await page.reload()
  await expect(page.locator('#forecast-panel').getByRole('alert')).toContainText('The forecast could not be loaded')
  apiModes.set(page, 'live-contract')
  await page.locator('#forecast-panel').getByRole('button', { name: 'Try again' }).click()
  await expect(page.getByTestId('forecast-plot')).toBeVisible()
  expect(signals.runtimeErrors).toEqual([])
  expect(signals.errors.every((error) => error.startsWith('Failed to load resource:') && error.includes('503'))).toBe(true)
})

test('reduced-motion preference suppresses transitions and loading animation', async ({ page }) => {
  apiModes.set(page, 'loading')
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/')
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
  pendingForecastReleases.get(page)?.()
})
