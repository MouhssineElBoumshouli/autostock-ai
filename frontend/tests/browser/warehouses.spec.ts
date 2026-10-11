import { expect, test, type Page, type Route } from '@playwright/test'

type Mode = 'normal' | 'empty' | 'no-results' | 'forbidden' | 'error'
const modes = new WeakMap<Page, Mode>()
const requests = new WeakMap<Page, string[]>()

const company = (id: number) => ({
  id,
  name: id === 1 ? 'Atlas Auto Distribution' : 'Atlas East Parts',
  logo_url: '',
  currency: { code: 'MAD', symbol: 'DH', decimal_places: 2 },
  demo_environment: true,
  demo_environment_note: 'Demonstration company.',
})

function warehouseRow(id: number, name: string, out = 0, low = 0) {
  return {
    id, name, code: id === 10 ? 'CENT' : 'EAST', company_name: 'Atlas Auto Distribution',
    catalog_parts: 1001, tracked_catalog_parts: 64, stocked_parts: 58, tracked_parts_present: 57,
    low_stock_parts: low, out_of_stock_parts: out, parts_with_reserved_stock: 17,
    parts_with_incoming_stock: 12, parts_with_outgoing_stock: 9,
    summary_complete: true, summary_note: false,
    status: out || low ? 'needs_attention' : 'healthy', recent_activity_at: '2026-10-10T14:00:00Z', activity_available: true,
  }
}

function warehousePage(companyId: number, url: URL, mode: Mode) {
  if (mode === 'empty' || (mode === 'no-results' && url.searchParams.get('q'))) {
    return {
      schema_version: 1, company: company(companyId), as_of: '2026-10-10 14:00:00',
      summary: { active_warehouses: 2, warehouses_needing_attention: 1, warehouses_with_low_stock: 1, warehouses_with_stockouts: 1, warehouses_with_incoming: 2, complete: true },
      filters: { query: url.searchParams.get('q') ?? '', status: url.searchParams.get('status') ?? 'all', sort: url.searchParams.get('sort') ?? 'attention', direction: url.searchParams.get('direction') ?? 'desc' },
      warehouses: [], pagination: { page: 1, page_size: 12, total_count: 0, total_pages: 0, has_previous: false, has_next: false },
      coverage: { summary_complete: true, catalog_product_count: 1001, catalog_scan_limit: 50000, warehouse_count: 2, warehouse_limit: 500, activity_available: true },
    }
  }
  const rows = [warehouseRow(10, 'Central Parts Warehouse', 8, 16), warehouseRow(11, 'East Distribution Hub')]
  const query = (url.searchParams.get('q') ?? '').toLowerCase()
  const status = url.searchParams.get('status') ?? 'all'
  const filtered = rows.filter((row) => (!query || `${row.name} ${row.code}`.toLowerCase().includes(query))
    && (status !== 'attention' || row.status === 'needs_attention')
    && (status !== 'low_stock' || row.low_stock_parts > 0)
    && (status !== 'out_of_stock' || row.out_of_stock_parts > 0)
    && (status !== 'healthy' || row.status === 'healthy'))
  if (url.searchParams.get('sort') === 'name' && url.searchParams.get('direction') === 'desc') filtered.reverse()
  const page = Number(url.searchParams.get('page') ?? 1)
  return {
    schema_version: 1, company: company(companyId), as_of: '2026-10-10 14:00:00',
    summary: { active_warehouses: 2, warehouses_needing_attention: 1, warehouses_with_low_stock: 1, warehouses_with_stockouts: 1, warehouses_with_incoming: 2, complete: true },
    filters: { query: url.searchParams.get('q') ?? '', status, sort: url.searchParams.get('sort') ?? 'attention', direction: url.searchParams.get('direction') ?? 'desc' },
    warehouses: filtered.slice((page - 1) * 12, page * 12),
    pagination: { page, page_size: 12, total_count: filtered.length, total_pages: Math.ceil(filtered.length / 12), has_previous: page > 1, has_next: page < Math.ceil(filtered.length / 12) },
    coverage: { summary_complete: true, catalog_product_count: 1001, catalog_scan_limit: 50000, warehouse_count: 2, warehouse_limit: 500, activity_available: true },
  }
}

function warehouseDetail(companyId: number, id: number) {
  const row = warehouseRow(id, id === 10 ? 'Central Parts Warehouse' : 'East Distribution Hub', 8, 16)
  return {
    schema_version: 1, company: company(companyId),
    warehouse: { id, name: row.name, code: row.code, company_name: row.company_name },
    summary: {
      catalog_parts: 1001, tracked_catalog_parts: 64, stocked_parts: 58, tracked_parts_present: 57,
      low_stock_parts: 16, out_of_stock_parts: 8, parts_with_reserved_stock: 17,
      parts_with_incoming_stock: 12, parts_with_outgoing_stock: 9, summary_complete: true,
      summary_note: false, reorder_suggestions: 7, reorder_suggestions_complete: true, reorder_suggestions_note: false,
    },
    attention_parts: [{ product_id: 1001, name: 'Alternator Assembly', sku: 'ALT-1001', uom: 'Units', status: 'out_of_stock', on_hand: 0, available: 0 }],
    activity_available: true,
    activity: [
      { id: 91, kind: 'received', label: 'Received', date: '2026-10-10T14:00:00Z', completed: true, product_id: 1001, product_name: 'Alternator Assembly', sku: 'ALT-1001', quantity: 12, uom: 'Units', reference: 'WH/IN/0091', counterpart_warehouse: false },
      { id: 92, kind: 'reserved_delivery', label: 'Reserved for customer orders', date: '2026-10-12T10:00:00Z', completed: false, product_id: 1002, product_name: 'Brake Rotor', sku: 'BR-1002', quantity: 4, uom: 'Pair', reference: 'SO/0142', counterpart_warehouse: false },
    ],
    activity_note: 'Completed changes cover the last 90 days. Expected moves are current planned activity.',
    as_of: '2026-10-10 14:00:00', read_only: true,
  }
}

function product(index: number) {
  const n = String(index + 1).padStart(4, '0')
  const onHand = index % 11 === 0 ? 0 : 18 + index
  const available = Math.max(0, onHand - 3)
  return {
    product_id: index + 1, template_id: index + 1, name: index === 1000 ? 'Alternator Assembly' : `Brake Rotor ${n}`,
    sku: index === 1000 ? 'ALT-1001' : `BR-${n}`, reference: `OEM-${n}`, category_id: 2, category: 'Brakes',
    tracked: true, active: true, uom: index % 2 ? 'Pair' : 'Units',
    status: onHand === 0 ? 'out_of_stock' : onHand < 20 ? 'low_stock' : 'in_stock',
    on_hand: onHand, available, reserved: onHand - available, incoming: index % 4 === 0 ? 6 : 0,
    outgoing: index % 3 === 0 ? 2 : 0, projected: onHand + (index % 4 === 0 ? 6 : 0), warehouse_count: 1,
    warehouses: [{ id: 10, name: 'Central Parts Warehouse', on_hand: onHand, available, reserved: onHand - available, incoming: index % 4 === 0 ? 6 : 0, outgoing: index % 3 === 0 ? 2 : 0 }],
    supplier: { id: 21, name: 'Northline Auto Supply', lead_time_days: 8, lead_time_label: 'Supplier lead time', minimum_order_qty: 1, minimum_order_uom: 'Units', company_specific: true },
    supplier_access_note: false, supplier_lookup_limited: false, lead_time_days: 8, lead_time_label: 'Supplier lead time', lead_time_source: 'supplier',
  }
}

function warehouseInventory(companyId: number, warehouseId: number, url: URL, mode: Mode) {
  const query = (url.searchParams.get('q') ?? '').toLowerCase()
  const supplierQuery = (url.searchParams.get('supplier_q') ?? '').toLowerCase()
  const status = url.searchParams.get('status') ?? 'all'
  const page = Number(url.searchParams.get('page') ?? 1)
  const size = Number(url.searchParams.get('page_size') ?? 25)
  const noResults = mode === 'empty' || (mode === 'no-results' && (query || supplierQuery)) || query.includes('no-match')
  const total = noResults ? 0 : query || supplierQuery ? 1 : 1001
  const index = query.includes('alt-1001') || query.includes('oem-1001') ? 1000 : (page - 1) * size
  const items = total ? Array.from({ length: Math.min(size, total - (page - 1) * size) }, (_, offset) => product(index + offset)) : []
  const filters = {
    query: url.searchParams.get('q') ?? '', supplier_query: url.searchParams.get('supplier_q') ?? '',
    status, warehouse_id: warehouseId, category_id: url.searchParams.has('category_id') ? Number(url.searchParams.get('category_id')) : false,
    supplier_id: false, tracked: url.searchParams.get('tracked') ?? 'all', active: 'active',
    sort: url.searchParams.get('sort') ?? 'name', direction: url.searchParams.get('direction') ?? 'asc',
  }
  return {
    schema_version: 1, company: company(companyId), as_of: '2026-10-10 14:00:00',
    summary: { total_tracked: 64, in_stock: 40, low_stock: 16, out_of_stock: 8, complete: true, sampled_products: 64, total_catalog: 1001 },
    filters,
    items,
    pagination: { page, page_size: size, total_count: total, total_pages: Math.ceil(total / size), has_previous: page > 1, has_next: page < Math.ceil(total / size), summary_exact: true, status_scan_used: status !== 'all' },
    coverage: { tracked_summary_complete: true, warehouse_scope_limited: false, supplier_lines_limited: false, supplier_terms_available: true, status_filter_complete: true },
    empty_catalog: mode === 'empty',
  }
}

function inventoryDetail(companyId: number, productId: number, warehouseId: number) {
  const row = product(productId - 1)
  const stock = { on_hand: row.on_hand, available: row.available, reserved: row.reserved, incoming: row.incoming, outgoing: row.outgoing, projected: row.projected }
  return {
    schema_version: 1, company: company(companyId),
    product: { id: productId, template_id: productId, name: row.name, sku: row.sku, reference: row.reference, category_id: 2, category: row.category, tracked: true, active: true, uom: row.uom, safety_stock: 5 },
    company_stock: stock,
    warehouses: [{ id: warehouseId, name: 'Central Parts Warehouse', ...stock, selected: true }],
    supplier: row.supplier, supplier_access: true, supplier_note: false, lead_time_days: 8, lead_time_label: 'Supplier lead time', lead_time_source: 'supplier',
    forecast: { status: 'not_used', message: 'No reviewed forecast was used for this part.', horizon_days: false, history_start: false, history_end: false, used_for_restock: false, demand_before_delivery: false },
    recommendations: [], recommendation_coverage: { complete: true, candidate_locations: 1, scanned_locations: 1, forecast_access_available: true, forecast_access_reason: false },
    movements_available: true, movements: [{ id: 91, kind: 'received', label: 'Received', date: '2026-10-10T14:00:00Z', quantity: 6, uom: row.uom, warehouse: 'Central Parts Warehouse', reference: 'WH/IN/0091' }],
    movement_note: 'Completed changes cover the last 90 days.', coverage: { warehouse_scope_limited: false, total_warehouses: 2, supplier_terms_available: true }, read_only: true,
  }
}

async function fulfill(route: Route, data: unknown, status = 200) {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) })
}

async function installApi(page: Page) {
  modes.set(page, 'normal')
  requests.set(page, [])
  await page.route('**/autostock/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname
    const companyId = Number(url.searchParams.get('company_id') ?? 1)
    const mode = modes.get(page) ?? 'normal'
    requests.get(page)?.push(route.request().url())
    if (mode === 'forbidden' && path.includes('/warehouses')) return fulfill(route, { error: { code: 'forbidden', message: 'Warehouse inventory access is required.' } }, 403)
    if (mode === 'error' && path.includes('/warehouses')) return fulfill(route, { error: { code: 'temporarily_unavailable', message: 'The warehouse service is temporarily unavailable.' } }, 503)
    if (path.endsWith('/session')) return fulfill(route, {
      schema_version: 1, authenticated: true,
      user: { id: 5, name: 'Alex Morgan', locale: 'en_US', timezone: 'UTC', permissions: { inventory: true, sales: true, inventory_manager: true } },
      current_company: company(companyId), allowed_companies: [company(1), company(2)],
    })
    if (path.endsWith('/inventory/options')) return fulfill(route, {
      schema_version: 1, company: company(companyId), warehouses: [{ id: 10, name: 'Central Parts Warehouse' }, { id: 11, name: 'East Distribution Hub' }], warehouse_options_limited: false, total_warehouses: 2,
      categories: [{ id: 2, name: 'Brakes' }], category_options_limited: false, suppliers: [{ id: 21, name: 'Northline Auto Supply' }], supplier_options_limited: false, supplier_access: true, supplier_access_note: false,
    })
    const warehouseStock = path.match(/\/warehouses\/(\d+)\/inventory$/)
    if (warehouseStock) return fulfill(route, warehouseInventory(companyId, Number(warehouseStock[1]), url, mode))
    const warehouseId = path.match(/\/warehouses\/(\d+)$/)
    if (warehouseId) return fulfill(route, warehouseDetail(companyId, Number(warehouseId[1])))
    if (path.endsWith('/warehouses')) return fulfill(route, warehousePage(companyId, url, mode))
    const productId = path.match(/\/products\/(\d+)\/inventory-detail$/)
    if (productId) return fulfill(route, inventoryDetail(companyId, Number(productId[1]), Number(url.searchParams.get('warehouse_id') ?? 10)))
    if (path.endsWith('/search/products')) return fulfill(route, {
      schema_version: 1, query: url.searchParams.get('q') ?? '', limited: false,
      results: [{ id: 1001, template_id: 1001, name: 'Alternator Assembly', sku: 'ALT-1001', reference: 'OEM-1001', category: 'Electrical', supplier_names: ['Northline Auto Supply'] }],
    })
    if (path.endsWith('/inventory')) return fulfill(route, warehouseInventory(companyId, 10, url, mode))
    return fulfill(route, { error: { code: 'not_found', message: 'Unknown test endpoint.' } }, 404)
  })
}

async function expectNoOverflow(page: Page, width: number) {
  const actual = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth, body: document.body.scrollWidth }))
  expect(actual.viewport).toBe(width)
  expect(actual.document).toBeLessThanOrEqual(width)
  expect(actual.body).toBeLessThanOrEqual(width)
}

test.beforeEach(async ({ page }) => installApi(page))

test('warehouse overview supports server search, attention filters, sorting, paging, and 1440/1024/390 layouts', async ({ page }) => {
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/warehouses')
    await expect(page.getByRole('heading', { name: 'Warehouses', level: 1 })).toBeVisible()
    await expect(page.getByText('2', { exact: true }).first()).toBeVisible()
    await expect(page.getByRole('link', { name: 'Open Central Parts Warehouse warehouse details' })).toBeVisible()
    await expectNoOverflow(page, width)
    if (width === 390) {
      await page.getByRole('button', { name: 'Open navigation menu' }).click()
      const nav = page.getByRole('dialog', { name: 'AutoStock navigation' })
      await expect(nav.getByRole('button', { name: 'Warehouses', exact: true })).toHaveAttribute('aria-current', 'page')
      await nav.getByRole('button', { name: 'Warehouses', exact: true }).click()
      await expect(page).toHaveURL('/warehouses')
    }
  }
  expect(pageErrors).toEqual([])

  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/warehouses')
  await page.getByRole('searchbox', { name: 'Search warehouses by name or code' }).fill('EAST')
  await expect(page.locator('.warehouse-card')).toHaveCount(1)
  await expect(page.locator('.warehouse-card')).toContainText('East Distribution Hub')
  await expect.poll(() => requests.get(page)?.some((request) => {
    const url = new URL(request)
    return url.pathname.endsWith('/warehouses') && url.searchParams.get('q') === 'EAST'
  })).toBe(true)
  await page.getByRole('searchbox', { name: 'Search warehouses by name or code' }).fill('')
  await page.getByRole('combobox', { name: 'Filter warehouses by stock status' }).selectOption('attention')
  await expect(page.locator('.warehouse-card')).toHaveCount(1)
  await expect(page.locator('.warehouse-card')).toContainText('Central Parts Warehouse')
  await page.getByRole('combobox', { name: 'Sort warehouses by' }).selectOption('name')
  await page.getByRole('button', { name: 'Sort ascending' }).click()
  await expect.poll(() => requests.get(page)?.some((request) => {
    const url = new URL(request)
    return url.pathname.endsWith('/warehouses') && url.searchParams.get('sort') === 'name' && url.searchParams.get('direction') === 'asc'
  })).toBe(true)
})

test('warehouse detail shows honest part counts, per-part stock, activity, pagination, and product details', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/warehouses/10')
  await expect(page.getByRole('heading', { name: 'Central Parts Warehouse', level: 1 })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Parts to check' })).toBeVisible()
  await expect(page.getByText('17', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('Available', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('not reserved', { exact: true }).first()).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Recent stock activity' })).toBeVisible()
  await expect(page.getByText('Received', { exact: true }).last()).toBeVisible()
  await expect(page.getByText('Reserved for customer orders')).toBeVisible()
  await expect(page.getByText('Current planned activity')).toBeVisible()
  await expect(page.getByRole('row', { name: /Brake Rotor 0001/ })).toContainText('Units')
  await expect(page.getByRole('row', { name: /Brake Rotor 0002/ })).toContainText('Pair')
  await page.getByRole('button', { name: 'Next parts page' }).click()
  await expect.poll(() => requests.get(page)?.some((request) => {
    const url = new URL(request)
    return url.pathname.endsWith('/warehouses/10/inventory') && url.searchParams.get('page') === '2'
  })).toBe(true)

  await page.getByRole('searchbox', { name: 'Search by part name, SKU, OEM reference' }).fill('ALT-1001')
  await expect(page.getByRole('row', { name: /Alternator Assembly/ })).toBeVisible()
  await expect.poll(() => requests.get(page)?.some((request) => {
    const url = new URL(request)
    return url.pathname.endsWith('/warehouses/10/inventory') && url.searchParams.get('q') === 'ALT-1001'
  })).toBe(true)
  await page.getByRole('combobox', { name: 'Filter warehouse parts by stock status' }).selectOption('out_of_stock')
  await page.getByRole('combobox', { name: 'Filter warehouse parts by category' }).selectOption('2')
  await page.getByRole('combobox', { name: 'Filter warehouse parts by monitoring' }).selectOption('tracked')
  await page.getByRole('combobox', { name: 'Filter warehouse parts by supplier' }).fill('Northline Auto Supply')
  await expect.poll(() => requests.get(page)?.some((request) => {
    const url = new URL(request)
    return url.pathname.endsWith('/warehouses/10/inventory') && url.searchParams.get('status') === 'out_of_stock'
      && url.searchParams.get('category_id') === '2' && url.searchParams.get('tracked') === 'tracked'
      && url.searchParams.get('supplier_q') === 'Northline Auto Supply'
  })).toBe(true)

  await page.getByRole('button', { name: /Open details for Alternator Assembly/ }).click()
  await expect(page.getByRole('dialog', { name: /Alternator Assembly/ })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Stock by warehouse' })).toBeVisible()
  await expect(page.getByRole('button', { name: /Create purchase|Adjust stock|Receive/ })).toHaveCount(0)
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 844 })
    await expectNoOverflow(page, width)
  }
})

test('warehouse inventory reaches product 1001 through server-side search and page requests', async ({ page }) => {
  await page.goto('/warehouses/10')
  await expect(page.getByText('1,001', { exact: true }).first()).toBeVisible()
  await page.getByRole('button', { name: 'Next parts page' }).click()
  await expect.poll(() => requests.get(page)?.some((request) => {
    const url = new URL(request)
    return url.pathname.endsWith('/warehouses/10/inventory') && url.searchParams.get('page') === '2'
  })).toBe(true)
  await page.getByRole('searchbox', { name: 'Search by part name, SKU, OEM reference' }).fill('ALT-1001')
  await expect(page.getByRole('row', { name: /Alternator Assembly/ })).toBeVisible()
  const filtered = requests.get(page)?.map((request) => new URL(request)).find((url) => url.pathname.endsWith('/warehouses/10/inventory') && url.searchParams.get('q') === 'ALT-1001')
  expect(filtered?.searchParams.get('page_size')).toBe('25')
})

test('warehouse overview and detail provide empty, permission, error, and navigation states', async ({ page }) => {
  modes.set(page, 'no-results')
  await page.goto('/warehouses')
  await page.getByRole('searchbox', { name: 'Search warehouses by name or code' }).fill('missing')
  await expect(page.getByRole('heading', { name: 'No warehouses match these filters' })).toBeVisible()

  modes.set(page, 'empty')
  await page.goto('/warehouses/10')
  await expect(page.getByRole('heading', { name: 'No parts are stored here yet' })).toBeVisible()

  modes.set(page, 'forbidden')
  await page.goto('/warehouses')
  await page.reload()
  await expect(page.getByRole('alert')).toContainText('Warehouse access is restricted')
  await page.goto('/warehouses/10')
  await page.reload()
  await expect(page.getByRole('alert')).toContainText('Warehouse access is restricted')

  modes.set(page, 'error')
  await page.goto('/warehouses')
  await page.reload()
  await expect(page.getByRole('alert')).toContainText('could not be loaded')
  await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible()

  modes.set(page, 'normal')
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/warehouses/10')
  await page.getByRole('button', { name: 'Open navigation menu' }).click()
  const navigation = page.getByRole('dialog', { name: 'AutoStock navigation' })
  await navigation.getByRole('button', { name: 'Inventory', exact: true }).click()
  await expect(page).toHaveURL(/\/inventory$/)
  await expect(page.getByRole('heading', { name: 'Inventory', level: 1 })).toBeVisible()
  await page.getByRole('button', { name: 'Open navigation menu' }).click()
  await page.getByRole('dialog', { name: 'AutoStock navigation' }).getByRole('button', { name: 'Warehouses', exact: true }).click()
  await expect(page).toHaveURL('/warehouses')
  await expect(page.getByRole('heading', { name: 'Warehouses', level: 1 })).toBeVisible()
  await expectNoOverflow(page, 390)
})

test('warehouse deep links and browser history work across Dashboard and Inventory', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/warehouses/10')
  await expect(page.getByRole('heading', { name: 'Central Parts Warehouse', level: 1 })).toBeVisible()
  await page.getByRole('link', { name: 'All warehouses' }).click()
  await expect(page).toHaveURL('/warehouses')
  await page.getByRole('button', { name: 'Inventory', exact: true }).click()
  await expect(page).toHaveURL('/inventory')
  await page.getByRole('button', { name: 'Dashboard', exact: true }).click()
  await expect(page).toHaveURL('/')

  await page.goBack()
  await expect(page).toHaveURL('/inventory')
  await page.goBack()
  await expect(page).toHaveURL('/warehouses')
  await page.goForward()
  await expect(page).toHaveURL('/inventory')
  await page.goForward()
  await expect(page).toHaveURL('/')

  await page.goto('/warehouses/10')
  await expect(page.getByRole('heading', { name: 'Central Parts Warehouse', level: 1 })).toBeVisible()
})
