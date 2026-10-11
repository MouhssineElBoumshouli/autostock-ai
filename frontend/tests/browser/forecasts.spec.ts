import { expect, test, type Page } from '@playwright/test'

const company = {
  id: 1, name: 'Atlas Auto Distribution', logo_url: '',
  currency: { code: 'MAD', symbol: 'DH', decimal_places: 2 },
  demo_environment: true, demo_environment_note: 'Fictional showroom data.',
}

function session() {
  return {
    schema_version: 1, authenticated: true,
    user: { id: 7, name: 'Atlas Stock Manager', locale: 'en_US', timezone: 'Africa/Casablanca', permissions: { inventory: true, sales: true, inventory_manager: true } },
    current_company: company, allowed_companies: [company],
  }
}

function savedRun(id: number, source: 'completed_deliveries' | 'synthetic_demo' = 'completed_deliveries', review: 'reviewed' | 'unreviewed' = 'reviewed') {
  return {
    id, product_id: source === 'synthetic_demo' ? false : 1001,
    product_name: source === 'synthetic_demo' ? 'Synthetic brake-pad example' : 'Front Brake Pad Set',
    sku: source === 'synthetic_demo' ? 'DEMO-BP-001' : 'BP-FR-420',
    warehouse_id: source === 'synthetic_demo' ? false : 10,
    warehouse_name: source === 'synthetic_demo' ? false : 'Atlas Central Warehouse',
    horizon_days: 30, history_start: '2026-03-01', history_end: '2026-09-26',
    source_cutoff: '2026-09-27 14:20:00', created_at: '2026-09-27 14:20:00',
    source_type: source, state: 'completed', evaluation_status: 'evaluated', review_status: review,
  }
}

function pageData(url: URL) {
  const all = [savedRun(14), savedRun(13, 'completed_deliveries', 'unreviewed'), savedRun(12, 'synthetic_demo')]
  const query = (url.searchParams.get('q') ?? '').toLowerCase()
  const warehouse = url.searchParams.get('warehouse_id')
  const horizon = url.searchParams.get('horizon_days')
  const state = url.searchParams.get('state')
  const review = url.searchParams.get('review_status')
  const source = url.searchParams.get('source_type')
  const rows = all.filter((run) => (!query || `${run.product_name} ${run.sku}`.toLowerCase().includes(query))
    && (!warehouse || run.warehouse_id === Number(warehouse))
    && (!horizon || horizon === 'all' || run.horizon_days === Number(horizon))
    && (!state || state === 'all' || run.state === state)
    && (!review || review === 'all' || run.review_status === review)
    && (!source || source === 'all' || run.source_type === source))
  const page = Number(url.searchParams.get('page') ?? 1)
  const pageSize = Number(url.searchParams.get('page_size') ?? 25)
  return {
    schema_version: 1, company,
    filters: {
      query: url.searchParams.get('q') ?? '',
      warehouse_id: warehouse ? Number(warehouse) : false,
      horizon_days: horizon && horizon !== 'all' ? Number(horizon) : 'all',
      state: state ?? 'all', review_status: review ?? 'all', source_type: source ?? 'all',
    },
    runs: rows.slice((page - 1) * pageSize, page * pageSize),
    pagination: { page, page_size: pageSize, total_count: rows.length, total_pages: Math.ceil(rows.length / pageSize), has_previous: page > 1, has_next: page < Math.ceil(rows.length / pageSize) },
    warehouse_options: [{ id: 10, name: 'Atlas Central Warehouse' }, { id: 11, name: 'Atlas East Warehouse' }],
    warehouse_options_limited: false, warehouse_count: 2,
    real_history_access: true, access_note: false, read_only: true,
  }
}

function detailData(id: number) {
  return {
    schema_version: 1, company,
    run: {
      id, name: 'BP-FR-420 · 30 days', company_id: 1, company_name: company.name,
      product_id: 1001, warehouse_id: 10, warehouse_name: 'Atlas Central Warehouse', uom: 'Units',
      created_at: '2026-09-27 14:20:00', state: 'completed', evaluation_status: 'evaluated', failure_reason: false,
      source_type: 'completed_deliveries', source_label: 'Completed deliveries, with returns recorded separately',
      sku: 'BP-FR-420', product_name: 'Front Brake Pad Set', horizon_days: 30,
      history_start: '2026-03-01', history_end: '2026-09-26', source_cutoff: '2026-09-27 14:20:00', source_timezone: 'UTC',
      history_days: 210, nonzero_days: 87, source_event_count: 129,
      source_snapshot_sha256: 'ab'.repeat(32), model_version: 'autostock-demand-v2.1.0',
      selected_method: 'trailing_mean', baseline_method: 'seasonal_naive', demand_pattern: 'regular', evaluation_days: 30,
      baseline_mae: 1.4, ml_mae: 1.15, ml_evaluated: true, review_status: 'reviewed',
      reviewed_by: 'Atlas Inventory Manager', reviewed_at: '2026-09-27 14:32:00',
      data_provenance: 'Completed Odoo stock moves linked to confirmed customer deliveries. Returns are separately recorded.',
      assumptions: 'Daily history records gross completed deliveries; zero recorded deliveries are treated as zero fulfilled sales.',
      limitations: 'Stockouts may censor fulfilled sales. Lost demand is not available in this source.',
      interval_note: 'The displayed range is a heuristic, not a calibrated confidence interval.',
      current_stock: { on_hand: 18, odoo_projected: 22, uom: 'Units' },
      observations: Array.from({ length: 45 }, (_, index) => {
        const date = new Date(Date.UTC(2026, 7, 12 + index)).toISOString().slice(0, 10)
        return { day: date, delivered_units: index % 7 === 0 ? 0 : 1 + (index % 5), returned_units: index === 19 ? 1 : 0, units: index % 7 === 0 ? 0 : 1 + (index % 5), source_event_count: index % 7 === 0 ? 0 : 1 }
      }),
      predictions: Array.from({ length: 30 }, (_, index) => {
        const date = new Date(Date.UTC(2026, 8, 27 + index)).toISOString().slice(0, 10)
        return { day: date, units: 2 + (index % 3), lower_heuristic: 1, upper_heuristic: 4 + index / 10 }
      }),
    },
    history_coverage: { configured: true, complete_from: '2026-02-01', run_starts_within_coverage: true },
    restock_guidance: { status: 'eligible', usable: true, reason: 'Reviewed, evaluated delivery history covers the supplier lead-time window.' },
    read_only: true,
  }
}

async function installSession(page: Page) {
  await page.route('**/autostock/api/v1/session*', (route) => route.fulfill({ json: session() }))
}

async function installForecastRoutes(page: Page) {
  await installSession(page)
  await page.route('**/autostock/api/v1/forecasts?**', (route) => route.fulfill({ json: pageData(new URL(route.request().url())) }))
  await page.route(/\/autostock\/api\/v1\/forecasts\/\d+(\?|$)/, (route) => {
    const id = Number(new URL(route.request().url()).pathname.split('/').at(-1))
    return route.fulfill({ json: detailData(id) })
  })
}

test('Forecasts overview filters on the server and fits desktop, tablet, and mobile', async ({ page }) => {
  await installForecastRoutes(page)
  const requests: URL[] = []
  page.on('request', (request) => {
    if (request.url().includes('/autostock/api/v1/forecasts?')) requests.push(new URL(request.url()))
  })
  const browserErrors: string[] = []
  page.on('pageerror', (error) => browserErrors.push(error.message))

  for (const [width, height] of [[1440, 1000], [1024, 900], [390, 844]]) {
    await page.setViewportSize({ width, height })
    await page.goto('/forecasts')
    await expect(page.getByRole('heading', { name: 'Forecasts', exact: true })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Saved forecasts' })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  }

  await page.setViewportSize({ width: 1440, height: 1000 })
  await expect(page.locator('.forecast-table tbody tr').filter({ hasText: 'DEMO-BP-001' })).toContainText('Synthetic showroom')
  await expect(page.locator('.forecast-table tbody tr').filter({ hasText: 'BP-FR-420' }).filter({ hasText: 'Needs review' })).toHaveCount(1)
  await page.getByRole('searchbox', { name: 'Search forecasts by part name or SKU' }).fill('BP-FR-420')
  await expect.poll(() => requests.some((request) => request.searchParams.get('q') === 'BP-FR-420')).toBe(true)
  await page.getByRole('combobox', { name: 'Filter forecasts by warehouse' }).selectOption('10')
  await expect.poll(() => requests.some((request) => request.searchParams.get('warehouse_id') === '10')).toBe(true)
  await page.getByRole('combobox', { name: 'Filter forecasts by horizon' }).selectOption('30')
  await expect.poll(() => requests.some((request) => request.searchParams.get('horizon_days') === '30')).toBe(true)
  await page.getByRole('combobox', { name: 'Filter forecasts by review status' }).selectOption('unreviewed')
  await expect.poll(() => requests.some((request) => request.searchParams.get('review_status') === 'unreviewed')).toBe(true)
  await page.getByRole('combobox', { name: 'Filter forecasts by source' }).selectOption('completed_deliveries')
  await expect.poll(() => requests.some((request) => request.searchParams.get('source_type') === 'completed_deliveries')).toBe(true)
  await expect(page.getByRole('link', { name: /Open forecast for Front Brake Pad Set/ }).first()).toBeVisible()
  expect(browserErrors).toEqual([])
})

test('forecast detail separates history, future estimates, provenance, and evaluation evidence', async ({ page }) => {
  await installForecastRoutes(page)
  const writes: string[] = []
  page.on('request', (request) => {
    if (request.url().includes('/autostock/api/') && request.method() !== 'GET') writes.push(request.method())
  })
  await page.goto('/forecasts/14')
  await expect(page.getByRole('heading', { name: 'Front Brake Pad Set', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Delivered history and forecast' })).toBeVisible()
  await expect(page.getByText('Forecast starts', { exact: true })).toBeVisible()
  await expect(page.getByText('Used for current restock guidance')).toBeVisible()
  await expect(page.getByText('History source', { exact: true })).toBeVisible()
  await page.getByText('How this forecast was calculated', { exact: true }).click()
  await expect(page.getByText('Chronological holdout', { exact: true })).toBeVisible()
  await expect(page.getByText(/comparison evidence for the saved series, not an independent accuracy claim/)).toBeVisible()
  await expect(page.getByText('Heuristic range', { exact: true }).first()).toBeVisible()
  await page.getByRole('link', { name: 'All forecasts' }).click()
  await expect(page).toHaveURL('/forecasts')
  expect(writes).toEqual([])
})

test('mobile navigation opens the Forecasts route and restricted/no-results states are readable', async ({ page }) => {
  await installForecastRoutes(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/forecasts')
  await page.getByRole('button', { name: 'Open navigation menu' }).click()
  await expect(page.getByRole('navigation', { name: 'Workspace' }).getByRole('button', { name: 'Forecasts' })).toHaveAttribute('aria-current', 'page')
  await page.getByRole('button', { name: 'Forecasts' }).last().click()
  await expect(page).toHaveURL('/forecasts')

  await page.getByRole('searchbox', { name: 'Search forecasts by part name or SKU' }).fill('no-such-part')
  await expect(page.getByRole('heading', { name: 'No forecasts match these filters' })).toBeVisible()
  await page.route('**/autostock/api/v1/forecasts?**', (route) => route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ error: { code: 'forbidden', message: 'Sales access is required.' } }) }))
  await page.goto('/forecasts')
  await expect(page.getByRole('heading', { name: 'Forecast history is restricted' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
})
