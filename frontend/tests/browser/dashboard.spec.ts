import { expect, test, type Page } from '@playwright/test'

const svgLogo = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="80" height="80" viewBox="0 0 80 80"%3E%3Crect width="80" height="80" rx="18" fill="%237656e8"/%3E%3Ctext x="50%25" y="58%25" text-anchor="middle" font-size="40" fill="white" font-family="Arial"%3EF%3C/text%3E%3C/svg%3E'

const makeCompany = (id: number, name: string) => ({
  id,
  name,
  logo_url: svgLogo,
  currency: { code: 'MAD', symbol: 'DH', decimal_places: 2 },
  demo_environment: true,
  demo_environment_note: 'Fictional data for frontend browser tests.',
})

const datesAgo = (days: number) => {
  const date = new Date('2026-10-10T12:00:00Z')
  date.setUTCDate(date.getUTCDate() - days)
  return date.toISOString().slice(0, 10)
}

function responseForCompany(id: number, horizon = 30) {
  const company = id === 2 ? makeCompany(2, 'Second Test Company') : makeCompany(1, 'Fixture Auto Parts')
  const history = Array.from({ length: 60 }, (_, index) => ({
    date: datesAgo(59 - index),
    units: index % 9 === 0 ? 0 : (index % 5) + 1,
  }))
  const endDate = new Date(`${history.at(-1)?.date}T12:00:00Z`)
  const predictions = Array.from({ length: horizon }, (_, index) => {
    const date = new Date(endDate)
    date.setUTCDate(date.getUTCDate() + index + 1)
    const units = (index % 4) + 2
    return { date: date.toISOString().slice(0, 10), units, lower: Math.max(0, units - 1), upper: units + 2 }
  })
  return {
    company,
    session: {
      schema_version: 1, authenticated: true,
      user: { id: 7, name: 'Demo Operator', locale: 'en_US', timezone: 'UTC', permissions: { inventory: true, sales: true, inventory_manager: false } },
      current_company: company,
      allowed_companies: [makeCompany(1, 'Fixture Auto Parts'), makeCompany(2, 'Second Test Company')],
    },
    dashboard: {
      schema_version: 1, company, snapshot_at: '2026-10-10 12:00 UTC',
      kpis: { tracked_products: id === 2 ? 18 : 64, in_stock: 42, low_stock: 16, out_of_stock: 6 },
      inventory_health: {
        total_tracked: id === 2 ? 18 : 64,
        sampled_products: id === 2 ? 18 : 64,
        complete: true,
        categories: [
          { key: 'healthy', label: 'In stock', count: 42 },
          { key: 'low', label: 'Low stock', count: 16 },
          { key: 'out', label: 'Out of stock', count: 6 },
        ],
      },
      empty: false,
    },
    forecast: {
      schema_version: 1, company, status: 'available', reason_code: false, message: false,
      forecast: {
        id: 19, product_name: 'Front Brake Rotor', sku: 'BRK-440', warehouse_name: 'Central warehouse',
        horizon_days: horizon, uom: 'Units', source_type: 'synthetic_demo', source_label: 'Synthetic demo',
        review_status: 'reviewed', evaluation_status: 'baseline_only',
        history_start: history[0].date, history_end: history.at(-1)!.date,
        history, predictions, limitations: 'Frontend browser fixture. Not a forecast-quality claim.',
      },
    },
    restock: {
      schema_version: 1, company, warehouse_id: false,
      warehouses: [{ id: 1, name: 'Central warehouse' }, { id: 2, name: 'North depot' }],
      as_of: '2026-10-10 12:00 UTC', read_only: true,
      summary: { priority_locations: 9, reorder_suggestions: 6, complete: true },
      items: [
        { key: '1:1', product_id: 1, template_id: 1, name: 'Front Brake Rotor', sku: 'BRK-440', warehouse_id: 1, warehouse: 'Central warehouse', status: 'low', status_label: 'Low stock', current_qty: 3, uom: 'Units', recommended_qty: 12, supplier_name: 'Fixture supplier', reason: 'Stock has reached the configured reorder trigger.', basis_note: 'Frontend browser fixture.', },
        { key: '2:1', product_id: 2, template_id: 2, name: 'Oil Filter Cartridge', sku: 'FLT-210', warehouse_id: 1, warehouse: 'Central warehouse', status: 'out', status_label: 'Out of stock', current_qty: 0, uom: 'Units', recommended_qty: 20, supplier_name: 'Fixture supplier', reason: 'No stock is on hand at this warehouse.', basis_note: 'Frontend browser fixture.', },
        { key: '3:2', product_id: 3, template_id: 3, name: 'Alternator Belt', sku: 'BEL-052', warehouse_id: 2, warehouse: 'North depot', status: 'shortage', status_label: 'Projected shortage', current_qty: 2, uom: 'Units', recommended_qty: false, supplier_name: false, reason: 'A reorder policy needs review.', basis_note: 'Frontend browser fixture.', },
      ],
      coverage: { complete: true, scanned_locations: 128, candidate_locations: 128, scan_limit: 500, flags: { warehouse_scope_limited: false, supplier_filter_limited: false, forecast_lookup_limited: false } },
    },
  }
}

async function installApiFixtures(page: Page) {
  await page.route('**/autostock/api/v1/session**', async (route) => {
    const companyId = Number(new URL(route.request().url()).searchParams.get('company_id') || 1)
    await route.fulfill({ json: responseForCompany(companyId).session })
  })
  await page.route('**/autostock/api/v1/dashboard/restock-preview**', async (route) => {
    const companyId = Number(new URL(route.request().url()).searchParams.get('company_id') || 1)
    await route.fulfill({ json: responseForCompany(companyId).restock })
  })
  await page.route('**/autostock/api/v1/dashboard/forecast-preview**', async (route) => {
    const url = new URL(route.request().url())
    const companyId = Number(url.searchParams.get('company_id') || 1)
    const horizon = Number(url.searchParams.get('horizon_days') || 30)
    await route.fulfill({ json: responseForCompany(companyId, horizon).forecast })
  })
  await page.route((url) => new URL(url).pathname === '/autostock/api/v1/dashboard', async (route) => {
    const companyId = Number(new URL(route.request().url()).searchParams.get('company_id') || 1)
    await route.fulfill({ json: responseForCompany(companyId).dashboard })
  })
  await page.route('**/autostock/api/v1/search/products**', async (route) => {
    await route.fulfill({ json: {
      schema_version: 1,
      query: new URL(route.request().url()).searchParams.get('q') || '',
      limited: false,
      results: [{ id: 1, template_id: 1, name: 'Front Brake Rotor', sku: 'BRK-440', reference: 'OEM-440' }],
    } })
  })
}

async function waitForDashboard(page: Page) {
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Demand Forecast' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Insights & Recommendations' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Reorder Recommendations' })).toBeVisible()
  await expect(page.locator('.chart-area svg')).toBeVisible()
  await expect(page.locator('.health-chart-wrap svg')).toBeVisible()
}

test('dashboard renders responsively without browser errors or clipped chart width', async ({ page }) => {
  const pageErrors: string[] = []
  const consoleErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
  await installApiFixtures(page)

  for (const viewport of [{ width: 1440, height: 960 }, { width: 1024, height: 768 }, { width: 390, height: 844 }, { width: 320, height: 800 }]) {
    await page.setViewportSize(viewport)
    await page.goto('/')
    await waitForDashboard(page)
    await expect(page.getByText('Demo environment', { exact: true })).toHaveCount(1)
    await expect(page.locator('.demo-pill')).toBeVisible()
    await expect(page.locator('.kpi-card')).toHaveCount(5)
    await expect(page.locator('.forecast-panel .panel-subtitle')).toContainText('next 30 days')
    await expect(page.getByRole('combobox', { name: 'Forecast horizon' })).toHaveValue('30')
    if (viewport.width === 1440) {
      const firstRow = page.locator('.reorder-row').first()
      await expect(firstRow.locator('.reorder-part strong')).toHaveText('Front Brake Rotor')
      await expect(firstRow.locator('.reorder-part > div > span')).toHaveText('BRK-440')
      await expect(firstRow).toContainText('Central warehouse')
      await expect(firstRow).toContainText('12 Units')
      await expect(page.locator('.insight-card')).toHaveCount(3)
      await firstRow.getByRole('button', { name: 'Review' }).click()
      await expect(page.getByRole('heading', { name: 'Front Brake Rotor' })).toBeVisible()
      await expect(page.getByText('Suggested reorder', { exact: true })).toBeVisible()
      await page.keyboard.press('Escape')
      await page.getByRole('combobox', { name: 'Forecast horizon' }).selectOption('60')
      await expect(page.getByRole('combobox', { name: 'Forecast horizon' })).toHaveValue('60')
      await expect(page.locator('.forecast-panel .panel-subtitle')).toContainText('next 60 days')
      const forecastDetails = page.locator('.forecast-details')
      await forecastDetails.locator('summary').click()
      await expect(forecastDetails.locator('.forecast-details-panel')).toContainText('Source: Synthetic demo')
      await expect(forecastDetails.locator('.forecast-details-panel')).toContainText('Not a forecast-quality claim')
      await forecastDetails.locator('summary').click()
    }
    if (viewport.width === 1440) {
      await page.locator('.chart-area').hover({ position: { x: 150, y: 100 } })
      await expect(page.locator('.forecast-panel .recharts-tooltip-wrapper')).toBeVisible()
      await page.mouse.move(5, 5)
    }
    const layout = await page.evaluate(() => {
      const svg = document.querySelector('.chart-area svg')
      const area = document.querySelector<HTMLElement>('.chart-area')
      const style = area ? getComputedStyle(area) : undefined
      return {
        viewport: window.innerWidth,
        document: document.documentElement.scrollWidth,
        chartWidth: svg?.getBoundingClientRect().width ?? 0,
        availableWidth: area && style
          ? area.clientWidth - Number.parseFloat(style.paddingLeft) - Number.parseFloat(style.paddingRight)
          : 0,
      }
    })
    expect(layout.document).toBeLessThanOrEqual(layout.viewport)
    expect(layout.chartWidth).toBeGreaterThan(layout.availableWidth - 4)
    if (viewport.width === 390) {
      const menuButton = page.getByRole('button', { name: 'Open navigation' })
      await expect(menuButton).toBeVisible()
      await expect(page.getByRole('button', { name: 'Search inventory' })).toBeVisible()
      await menuButton.click()
      await expect(page.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible()
      await page.getByRole('button', { name: 'Close' }).click()
    }
  }
  expect(pageErrors).toEqual([])
  expect(consoleErrors).toEqual([])
})

test('company switcher scopes the refreshed dashboard to the selected company', async ({ page }) => {
  await installApiFixtures(page)
  await page.goto('/')
  await waitForDashboard(page)
  await page.getByLabel('Current company').selectOption('2')
  await expect(page.getByLabel('Current company')).toHaveValue('2')
  await expect(page.getByText('18', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Current company')).toContainText('Second Test Company')
})

test('global product search returns an Odoo-backed result and opens its product record', async ({ page }) => {
  await installApiFixtures(page)
  await page.route('**/web', (route) => route.fulfill({ contentType: 'text/html', body: '<!doctype html><title>Odoo product record</title>' }))
  await page.goto('/')
  await waitForDashboard(page)
  await page.getByRole('button', { name: 'Search inventory' }).click()
  const search = page.getByPlaceholder('Search by part name, SKU, or OEM reference…')
  await search.fill('BRK')
  await expect(page.getByRole('option', { name: /Front Brake Rotor/ })).toBeVisible()
  await page.getByRole('option', { name: /Front Brake Rotor/ }).click()
  await expect(page).toHaveURL(/\/web#id=1&model=product.product&view_type=form/)
})
