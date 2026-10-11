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

function estimate(status: 'missing' | 'incomplete' | 'not_completed' | 'available', horizon: 7 | 30 | 60) {
  if (status === 'available') return {
    status, estimated_units: horizon * 2.4, uom: 'Units', uom_rounding: 1,
    date_start: '2026-09-27', date_end: horizon === 7 ? '2026-10-03' : horizon === 30 ? '2026-10-26' : '2026-11-25',
    window_status: 'in_progress',
  }
  return { status, estimated_units: false, uom: status === 'missing' ? false : 'Units', uom_rounding: status === 'missing' ? false : 1, date_start: false, date_end: false, window_status: false }
}

function partRun(id: number, horizon: 7 | 30 | 60, state: 'completed' | 'failed', review: 'reviewed' | 'unreviewed') {
  return { id, created_at: id === 15 ? '2026-10-01 15:00:00' : '2026-09-27 14:20:00', horizon_days: horizon, source_type: 'completed_deliveries', state, evaluation_status: state === 'completed' ? 'evaluated' : 'failed', review_status: review }
}

function part(productId = 1001, warehouseId = 10, productName = 'Front Brake Pad Set', sku = 'BP-FR-420') {
  return {
    product_id: productId, product_name: productName, sku,
    warehouse_id: warehouseId, warehouse_name: warehouseId === 10 ? 'Atlas Central Warehouse' : 'Atlas East Warehouse',
    source_type: 'completed_deliveries',
    horizons: [
      { horizon_days: 7, saved_run_count: 0, latest_run: false, estimate: estimate('missing', 7) },
      { horizon_days: 30, saved_run_count: 1, latest_run: partRun(warehouseId === 10 ? 14 : 24, 30, 'completed', 'reviewed'), estimate: estimate('available', 30) },
      { horizon_days: 60, saved_run_count: 2, latest_run: partRun(15, 60, 'completed', 'unreviewed'), estimate: estimate('incomplete', 60) },
    ],
  }
}

function partPageData(url: URL) {
  const query = (url.searchParams.get('q') ?? '').toLowerCase()
  const warehouse = url.searchParams.get('warehouse_id')
  const all = [
    part(),
    part(1002, 11, 'Front Brake Pad Set', 'BP-FR-420'),
    part(1003, 10, 'Plaquettes renforcées pour utilitaires et véhicules de flotte', 'FR-LONG-03'),
  ]
  const parts = all.filter((item) => (!query || `${item.product_name} ${item.sku}`.toLowerCase().includes(query))
    && (!warehouse || item.warehouse_id === Number(warehouse)))
  const page = Number(url.searchParams.get('page') ?? 1)
  const pageSize = Number(url.searchParams.get('page_size') ?? 12)
  return {
    schema_version: 1, company,
    filters: { query: url.searchParams.get('q') ?? '', warehouse_id: warehouse ? Number(warehouse) : false },
    parts: parts.slice((page - 1) * pageSize, page * pageSize),
    pagination: { page, page_size: pageSize, has_previous: page > 1, has_next: page < Math.ceil(parts.length / pageSize) },
    warehouse_options: [{ id: 10, name: 'Atlas Central Warehouse' }, { id: 11, name: 'Atlas East Warehouse' }],
    warehouse_options_limited: false, warehouse_count: 2, real_history_access: true, access_note: false, read_only: true,
  }
}

function savedRun(id: number, source: 'completed_deliveries' | 'synthetic_demo' = 'completed_deliveries', state: 'completed' | 'failed' = 'completed', review: 'reviewed' | 'unreviewed' = 'reviewed') {
  const isDemo = source === 'synthetic_demo'
  return {
    id, product_id: isDemo ? false : 1001,
    product_name: isDemo ? 'Front Brake Pad Set' : 'Front Brake Pad Set',
    sku: 'BP-FR-420',
    warehouse_id: isDemo ? false : 10,
    warehouse_name: isDemo ? false : 'Atlas Central Warehouse',
    horizon_days: 30, history_start: '2026-03-01', history_end: '2026-09-26',
    source_cutoff: '2026-09-27 14:20:00', created_at: id === 15 ? '2026-10-01 15:00:00' : '2026-09-27 14:20:00',
    source_type: source, state, evaluation_status: state === 'completed' ? 'evaluated' : 'failed', review_status: review,
  }
}

function historyPageData(url: URL) {
  const all = [savedRun(15, 'completed_deliveries', 'failed', 'unreviewed'), savedRun(14), savedRun(12, 'synthetic_demo')]
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
  const totalPages = Math.ceil(rows.length / pageSize)
  return {
    schema_version: 1, company,
    filters: { query: url.searchParams.get('q') ?? '', warehouse_id: warehouse ? Number(warehouse) : false, horizon_days: horizon && horizon !== 'all' ? Number(horizon) : 'all', state: state ?? 'all', review_status: review ?? 'all', source_type: source ?? 'all' },
    runs: rows.slice((page - 1) * pageSize, page * pageSize),
    pagination: { page, page_size: pageSize, total_count: rows.length, total_pages: totalPages, has_previous: page > 1, has_next: page < totalPages },
    warehouse_options: [{ id: 10, name: 'Atlas Central Warehouse' }, { id: 11, name: 'Atlas East Warehouse' }],
    warehouse_options_limited: false, warehouse_count: 2, real_history_access: true, access_note: false, read_only: true,
  }
}

function detailData(id: number, reviewStatus: 'reviewed' | 'unreviewed' = 'reviewed') {
  return {
    schema_version: 1, company,
    estimate: id === 14 ? estimate('available', 30) : estimate('incomplete', 60),
    run: {
      id, name: 'BP-FR-420 · 30 days', company_id: 1, company_name: company.name,
      product_id: 1001, warehouse_id: 10, warehouse_name: 'Atlas Central Warehouse', uom: 'Units',
      created_at: '2026-09-27 14:20:00', state: 'completed', evaluation_status: 'evaluated', failure_reason: false,
      source_type: 'completed_deliveries', source_label: 'Completed deliveries, with returns recorded separately',
      sku: 'BP-FR-420', product_name: 'Front Brake Pad Set', horizon_days: id === 14 ? 30 : 60,
      history_start: '2026-03-01', history_end: '2026-09-26', source_cutoff: '2026-09-27 14:20:00', source_timezone: 'UTC',
      history_days: 210, nonzero_days: 87, source_event_count: 129,
      source_snapshot_sha256: 'ab'.repeat(32), model_version: 'autostock-demand-v2.1.0',
      selected_method: 'trailing_mean', baseline_method: 'seasonal_naive', demand_pattern: 'regular', evaluation_days: 30,
      baseline_mae: 1.4, ml_mae: 1.15, ml_evaluated: true, review_status: reviewStatus,
      reviewed_by: reviewStatus === 'reviewed' ? 'Atlas Inventory Manager' : false, reviewed_at: reviewStatus === 'reviewed' ? '2026-09-27 14:32:00' : false,
      data_provenance: 'Completed Odoo stock moves linked to confirmed customer deliveries. Returns are separately recorded.',
      assumptions: 'Daily history records gross completed deliveries; zero recorded deliveries are treated as zero fulfilled sales.',
      limitations: 'Stockouts may censor fulfilled sales. Lost demand is not available in this source.',
      interval_note: 'The displayed range is a heuristic, not a calibrated confidence interval.',
      current_stock: { on_hand: 18, odoo_projected: 22, uom: 'Units' },
      observations: Array.from({ length: 45 }, (_, index) => {
        const date = new Date(Date.UTC(2026, 7, 12 + index)).toISOString().slice(0, 10)
        return { day: date, delivered_units: index % 7 === 0 ? 0 : 1 + (index % 5), returned_units: index === 19 ? 1 : 0, units: index % 7 === 0 ? 0 : 1 + (index % 5), source_event_count: index % 7 === 0 ? 0 : 1 }
      }),
      predictions: id === 14 ? Array.from({ length: 30 }, (_, index) => {
        const date = new Date(Date.UTC(2026, 8, 27 + index)).toISOString().slice(0, 10)
        return { day: date, units: 2 + (index % 3), lower_heuristic: 1, upper_heuristic: 4 + index / 10 }
      }) : [{ day: '2026-09-27', units: 2, lower_heuristic: 1, upper_heuristic: 3 }],
    },
    history_coverage: { configured: true, complete_from: '2026-02-01', run_starts_within_coverage: true },
    restock_guidance: { status: 'not_eligible', usable: false, reason: 'Current guidance selected a different saved run.' },
    read_only: true,
  }
}

async function installSession(page: Page) {
  await page.route('**/autostock/api/v1/session*', (route) => route.fulfill({ json: session() }))
}

async function installForecastRoutes(page: Page) {
  await installSession(page)
  await page.route('**/autostock/api/v1/forecasts/parts?**', (route) => route.fulfill({ json: partPageData(new URL(route.request().url())) }))
  await page.route('**/autostock/api/v1/forecasts?**', (route) => route.fulfill({ json: historyPageData(new URL(route.request().url())) }))
  await page.route(/\/autostock\/api\/v1\/forecasts\/\d+(\?|$)/, (route) => {
    const id = Number(new URL(route.request().url()).pathname.split('/').at(-1))
    return route.fulfill({ json: detailData(id, id === 15 ? 'unreviewed' : 'reviewed') })
  })
}

test('part-first Forecasts fits desktop, tablet and mobile and sends search and warehouse filters to Odoo', async ({ page }) => {
  await installForecastRoutes(page)
  const requests: URL[] = []
  const browserErrors: string[] = []
  page.on('request', (request) => {
    if (request.url().includes('/autostock/api/v1/forecasts/parts?')) requests.push(new URL(request.url()))
  })
  page.on('pageerror', (error) => browserErrors.push(error.message))

  for (const [width, height] of [[1440, 1000], [1024, 900], [390, 844]]) {
    await page.setViewportSize({ width, height })
    await page.goto('/forecasts')
    await expect(page.getByRole('heading', { name: 'Forecasts', exact: true })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Forecasts by part' })).toBeVisible()
    await expect(page.locator('.forecast-part-row')).toHaveCount(3)
    expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  }

  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.getByRole('searchbox', { name: 'Search forecast parts by name or SKU' }).fill('BP-FR-420')
  await expect.poll(() => requests.some((request) => request.searchParams.get('q') === 'BP-FR-420')).toBe(true)
  await page.getByRole('combobox', { name: 'Choose forecast warehouse' }).selectOption('10')
  await expect.poll(() => requests.some((request) => request.searchParams.get('warehouse_id') === '10')).toBe(true)
  await expect(page.locator('.forecast-part-row')).toHaveCount(1)
  expect(browserErrors).toEqual([])
})

test('forecast period controls show saved totals only for full daily series', async ({ page }) => {
  await installForecastRoutes(page)
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/forecasts')
  const row = page.locator('.forecast-part-row').filter({ hasText: 'Atlas Central Warehouse' }).first()
  await expect(row.getByTestId('forecast-estimated-total')).toContainText('72 Units')
  await expect(row.getByTestId('forecast-estimate-range')).toContainText('Sep 27, 2026')
  await row.getByRole('button', { name: '60 days' }).click()
  await expect(row).toContainText('A complete daily estimate is not available, so a total cannot be shown.')
  await expect(row.getByTestId('forecast-estimated-total')).toHaveCount(0)
  await expect(row).toContainText('Needs review')
  await row.getByRole('button', { name: '7 days' }).click()
  await expect(row).toContainText('No 7-day estimate is saved for this part and warehouse.')
  await expect(row.getByTestId('forecast-estimated-total')).toHaveCount(0)
})

test('saved history separates synthetic examples and exposes every review and run state', async ({ page }) => {
  await installForecastRoutes(page)
  await page.goto('/forecasts')
  await page.getByRole('button', { name: 'Saved run history' }).click()
  await expect(page.getByRole('heading', { name: 'Saved run history' })).toBeVisible()
  await expect(page.locator('.forecast-table tbody tr')).toHaveCount(3)
  const demoRow = page.locator('.forecast-table tbody tr').filter({ hasText: 'Synthetic demo example' })
  await expect(demoRow).toContainText('BP-FR-420')
  await expect(page.locator('.forecast-table tbody tr').filter({ hasText: 'Needs review' })).toHaveCount(1)
  await page.getByText('More filters', { exact: true }).click()
  await page.getByRole('combobox', { name: 'Filter forecasts by run status' }).selectOption('failed')
  await expect(page.locator('.forecast-table tbody tr')).toHaveCount(1)
  await expect(page.locator('.forecast-table tbody tr').first()).toContainText('Needs review')
})

test('forecast detail leads with the exact saved estimate and keeps evidence collapsed', async ({ page }) => {
  await installForecastRoutes(page)
  const writes: string[] = []
  const browserErrors: string[] = []
  page.on('request', (request) => {
    if (request.url().includes('/autostock/api/') && request.method() !== 'GET') writes.push(request.method())
  })
  page.on('pageerror', (error) => browserErrors.push(error.message))
  await page.goto('/forecasts/14?view=history')
  await expect(page.getByRole('heading', { name: 'Front Brake Pad Set', exact: true })).toBeVisible()
  await expect(page.getByText('Atlas Central Warehouse · Atlas Auto Distribution')).toBeVisible()
  await expect(page.getByText('Estimated deliveries', { exact: true })).toBeVisible()
  await expect(page.getByTestId('forecast-estimated-total')).toHaveText('72 Units')
  await expect(page.getByText('Reviewed', { exact: true })).toBeVisible()
  await expect(page.getByText('This saved estimate is not currently used for restock guidance.')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Past deliveries and saved estimate' })).toBeVisible()
  await expect(page.getByText('Forecast starts', { exact: true })).toBeVisible()
  await expect(page.locator('.forecast-chart-wrap')).toHaveAttribute('data-first-forecast-day', '2026-09-27')
  await expect(page.locator('.forecast-chart-wrap')).toHaveAttribute('data-first-forecast-units', '2')
  const disclosure = page.locator('.forecast-evaluation-disclosure')
  await expect(disclosure).not.toHaveAttribute('open', '')
  await expect(disclosure.getByText('Chronological holdout', { exact: true })).toBeHidden()
  await disclosure.locator('summary').click()
  await expect(disclosure.getByText('Chronological holdout', { exact: true })).toBeVisible()
  await expect(disclosure).toContainText('Source cutoff (your local time)')
  await expect(disclosure).toContainText('Source snapshot')
  await expect(disclosure).toContainText('MAE is the average absolute daily error')
  await expect(page.getByRole('link', { name: 'Back to forecasts' })).toHaveAttribute('href', /view=history/)
  await page.getByRole('link', { name: 'Back to forecasts' }).click()
  await expect(page).toHaveURL(/\/forecasts\?view=history/)
  expect(writes).toEqual([])
  expect(browserErrors).toEqual([])
})

test('detail never invents a total or future wording for a one-day partial run', async ({ page }) => {
  await installForecastRoutes(page)
  await page.goto('/forecasts/15')
  await expect(page.getByRole('heading', { name: 'Front Brake Pad Set', exact: true })).toBeVisible()
  await expect(page.getByText('Needs review', { exact: true })).toBeVisible()
  await expect(page.getByTestId('forecast-estimate-unavailable')).toContainText('only 1 of 60 daily estimates are saved')
  await expect(page.getByTestId('forecast-estimated-total')).toHaveCount(0)
  await expect(page.getByText(/next 60 days|next 2 months/i)).toHaveCount(0)
})

test('completed saved estimates with an ended date range are labeled as past periods', async ({ page }) => {
  await installForecastRoutes(page)
  await page.route('**/autostock/api/v1/forecasts/parts?**', async (route) => {
    const data = partPageData(new URL(route.request().url()))
    for (const item of data.parts) {
      const thirtyDay = item.horizons.find((horizon) => horizon.horizon_days === 30)
      if (thirtyDay?.estimate.status === 'available') {
        thirtyDay.estimate = { ...thirtyDay.estimate, date_start: '2025-01-01', date_end: '2025-01-30', window_status: 'ended' }
      }
    }
    await route.fulfill({ json: data })
  })
  await page.route(/\/autostock\/api\/v1\/forecasts\/14(\?|$)/, (route) => {
    const detail = detailData(14)
    detail.estimate = { ...detail.estimate, date_start: '2025-01-01', date_end: '2025-01-30', window_status: 'ended' }
    return route.fulfill({ json: detail })
  })
  await page.goto('/forecasts')
  const row = page.locator('.forecast-part-row').first()
  await expect(row).toContainText('This saved estimate period has ended.')
  await expect(row).not.toContainText(/next 30 days/i)
  await row.getByRole('link', { name: /Open 30-day estimate/ }).click()
  await expect(page.getByText('This saved period has ended.', { exact: true })).toBeVisible()
  await expect(page.getByText(/next 30 days/i)).toHaveCount(0)
})

test('mobile navigation, no-history state, permission state, and long names remain usable', async ({ page }) => {
  await installForecastRoutes(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/forecasts')
  await page.getByRole('button', { name: 'Open navigation menu' }).click()
  await expect(page.getByRole('navigation', { name: 'Workspace' }).getByRole('button', { name: 'Forecasts' })).toHaveAttribute('aria-current', 'page')
  await page.getByRole('button', { name: 'Forecasts' }).last().click()
  await expect(page.getByRole('heading', { name: 'Forecasts by part' })).toBeVisible()
  await expect(page.locator('.forecast-part-row').filter({ hasText: 'Plaquettes renforcées' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)

  await page.route('**/autostock/api/v1/forecasts/parts?**', (route) => route.fulfill({ json: { ...partPageData(new URL(route.request().url())), parts: [], access_note: false } }))
  await page.getByRole('searchbox', { name: 'Search forecast parts by name or SKU' }).fill('no-such-part')
  await expect(page.getByRole('heading', { name: 'No parts match your search' })).toBeVisible()
  await page.route('**/autostock/api/v1/forecasts/parts?**', (route) => route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ error: { code: 'forbidden', message: 'Inventory access is required.' } }) }))
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Forecasts are restricted' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
})

test('Saved run timestamps use the authenticated session timezone on desktop and mobile', async ({ page }) => {
  await installForecastRoutes(page)
  const expected = await page.evaluate(() => {
    const instant = new Date('2026-09-27T14:20:00Z')
    return {
      date: new Intl.DateTimeFormat(undefined, { timeZone: 'Africa/Casablanca', month: 'short', day: 'numeric', year: 'numeric' }).format(instant),
      mobileDate: new Intl.DateTimeFormat(undefined, { timeZone: 'Africa/Casablanca', month: 'short', day: 'numeric' }).format(instant),
      time: new Intl.DateTimeFormat(undefined, { timeZone: 'Africa/Casablanca', hour: 'numeric', minute: '2-digit' }).format(instant),
    }
  })
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/forecasts?view=history')
    if (width <= 760) {
      const card = page.locator('.forecast-mobile-card').filter({ hasText: 'BP-FR-420' }).nth(1)
      await expect(card.getByTestId('forecast-saved-date')).toHaveText(expected.mobileDate)
    } else {
      const row = page.locator('.forecast-table tbody tr').filter({ hasText: 'BP-FR-420' }).nth(1)
      await expect(row.getByTestId('forecast-saved-date')).toHaveText(expected.date)
      await expect(row.getByTestId('forecast-saved-time')).toHaveText(expected.time)
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  }
})
