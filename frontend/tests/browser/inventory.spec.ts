import { expect, test, type Page, type Route } from '@playwright/test'

type Mode = 'catalog' | 'empty' | 'no-results' | 'forbidden' | 'error'
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

function item(index: number) {
  const onHand = index % 11 === 0 ? 0 : 22 + index
  const available = Math.max(0, onHand - (index % 3))
  const supplier = index % 2 === 0 ? 'Northline Auto Supply' : 'Atlas Components'
  const partNumber = String(index + 1).padStart(4, '0')
  return {
    product_id: index + 1,
    template_id: index + 1,
    name: 'Brake Pad ' + partNumber,
    sku: 'BP-' + partNumber,
    reference: 'OEM-BP-' + (index + 1),
    category_id: 2,
    category: 'Brakes',
    tracked: true,
    active: true,
    uom: 'Units',
    status: onHand <= 0 ? 'out_of_stock' : onHand <= 25 ? 'low_stock' : 'in_stock',
    on_hand: onHand,
    available,
    reserved: onHand - available,
    incoming: index % 5 === 0 ? 12 : 0,
    outgoing: index % 3,
    projected: onHand + (index % 5 === 0 ? 12 : 0) - (index % 3),
    warehouse_count: 1,
    warehouses: [{
      id: 10, name: 'Central Warehouse', on_hand: onHand, available,
      reserved: onHand - available, incoming: index % 5 === 0 ? 12 : 0, outgoing: index % 3,
    }],
    supplier: {
      id: index % 2 === 0 ? 21 : 22,
      name: supplier,
      lead_time_days: 8,
      lead_time_label: 'Supplier lead time',
      minimum_order_qty: 1,
      minimum_order_uom: 'Units',
      company_specific: true,
    },
    supplier_access_note: false,
    supplier_lookup_limited: false,
    lead_time_days: 8,
    lead_time_label: 'Supplier lead time',
    lead_time_source: 'supplier',
  }
}

function inventoryPayload(companyId: number, url: URL, mode: Mode) {
  const query = (url.searchParams.get('q') ?? '').toLowerCase()
  if (mode === 'empty' || mode === 'no-results' || query.includes('not-a-real-part')) {
    return {
      schema_version: 1, company: company(companyId), as_of: new Date().toISOString(),
      summary: { total_tracked: 0, in_stock: 0, low_stock: 0, out_of_stock: 0, complete: true, sampled_products: 0, total_catalog: 0 },
      filters: { query, supplier_query: '', status: 'all', warehouse_id: false, category_id: false, supplier_id: false, tracked: 'all', active: 'active', sort: 'name', direction: 'asc' },
      items: [],
      pagination: { page: 1, page_size: 25, total_count: 0, total_pages: 0, has_previous: false, has_next: false, summary_exact: true, status_scan_used: false },
      coverage: { tracked_summary_complete: true, warehouse_scope_limited: false, supplier_lines_limited: false, supplier_terms_available: true, status_filter_complete: true },
      empty_catalog: mode === 'empty',
    }
  }

  const size = Number(url.searchParams.get('page_size') ?? 25)
  const page = Number(url.searchParams.get('page') ?? 1)
  let firstIndex = (page - 1) * size
  let total = 1001
  if (query || url.searchParams.has('supplier_q')) {
    firstIndex = query.includes('bp-1001') || query.includes('oem-bp-1001') ? 1000 : 0
    total = 1
  }
  const pageCount = Math.ceil(total / size)
  const count = query || url.searchParams.has('supplier_q')
    ? total
    : Math.max(0, Math.min(size, total - firstIndex))
  const items = Array.from({ length: count }, (_, offset) => item(firstIndex + offset))
  return {
    schema_version: 1, company: company(companyId), as_of: new Date().toISOString(),
    summary: { total_tracked: 930, in_stock: 810, low_stock: 90, out_of_stock: 30, complete: true, sampled_products: 930, total_catalog: 1001 },
    filters: {
      query, supplier_query: url.searchParams.get('supplier_q') ?? '', status: url.searchParams.get('status') ?? 'all',
      warehouse_id: url.searchParams.has('warehouse_id') ? Number(url.searchParams.get('warehouse_id')) : false,
      category_id: url.searchParams.has('category_id') ? Number(url.searchParams.get('category_id')) : false,
      supplier_id: false, tracked: url.searchParams.get('tracked') ?? 'all', active: url.searchParams.get('active') ?? 'active',
      sort: url.searchParams.get('sort') ?? 'name', direction: url.searchParams.get('direction') ?? 'asc',
    },
    items,
    pagination: {
      page, page_size: size, total_count: total, total_pages: pageCount,
      has_previous: page > 1, has_next: page < pageCount, summary_exact: true, status_scan_used: url.searchParams.get('status') === 'low_stock',
    },
    coverage: { tracked_summary_complete: true, warehouse_scope_limited: false, supplier_lines_limited: false, supplier_terms_available: true, status_filter_complete: true },
    empty_catalog: false,
  }
}

function detailPayload(companyId: number, productId: number) {
  const product = item(productId - 1)
  return {
    schema_version: 1,
    company: company(companyId),
    product: {
      id: productId, template_id: productId, name: product.name, sku: product.sku, reference: product.reference,
      category_id: 2, category: 'Brakes', tracked: true, active: true, uom: 'Units', safety_stock: 20,
    },
    company_stock: { on_hand: 24, available: 18, reserved: 6, incoming: 12, outgoing: 2, projected: 34 },
    warehouses: [{
      id: 10, name: 'Central Warehouse', on_hand: 24, available: 18, reserved: 6, incoming: 12, outgoing: 2, selected: true, projected: 34,
    }],
    supplier: { id: 21, name: 'Northline Auto Supply', lead_time_days: 8, lead_time_label: 'Supplier lead time', minimum_order_qty: 1, minimum_order_uom: 'Units', company_specific: true },
    supplier_access: true, supplier_note: false,
    lead_time_days: 8, lead_time_label: 'Supplier lead time', lead_time_source: 'supplier',
    forecast: { status: 'used', message: 'A reviewed delivery forecast contributed demand through the expected delivery date.', horizon_days: 30, history_start: '2026-09-01', history_end: '2026-09-30', used_for_restock: true, demand_before_delivery: 4 },
    recommendations: [],
    recommendation_coverage: { complete: true, candidate_locations: 1, scanned_locations: 1, forecast_access_available: true, forecast_access_reason: false },
    movements_available: true,
    movements: [{
      id: 88, kind: 'received', label: 'Received', date: '2026-10-08T09:00:00Z', quantity: 12, uom: 'Units',
      warehouse: 'Central Warehouse', reference: 'PO/2026/088',
    }],
    movement_note: 'Showing the latest 20 relevant movements from the last 90 days.',
    coverage: { warehouse_scope_limited: false, total_warehouses: 1, supplier_terms_available: true },
    read_only: true,
  }
}

async function fulfill(route: Route, payload: unknown, status = 200) {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(payload) })
}

async function installApi(page: Page) {
  modes.set(page, 'catalog')
  requests.set(page, [])
  await page.route('**/autostock/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname
    const companyId = Number(url.searchParams.get('company_id') ?? 1)
    const mode = modes.get(page) ?? 'catalog'
    requests.get(page)?.push(route.request().url())

    if (path.endsWith('/session')) {
      return fulfill(route, {
        schema_version: 1, authenticated: true,
        user: { id: 5, name: 'Alex Morgan', locale: 'en_US', timezone: 'UTC', permissions: { inventory: true, sales: true, inventory_manager: true } },
        current_company: company(companyId), allowed_companies: [company(1), company(2)],
      })
    }
    if (path.endsWith('/inventory/options')) {
      return fulfill(route, {
        schema_version: 1, company: company(companyId),
        warehouses: [{ id: 10, name: 'Central Warehouse' }], warehouse_options_limited: false, total_warehouses: 1,
        categories: [{ id: 2, name: 'Brakes' }], category_options_limited: false,
        suppliers: [{ id: 21, name: 'Northline Auto Supply' }, { id: 22, name: 'Atlas Components' }],
        supplier_options_limited: false, supplier_access: true, supplier_access_note: false,
      })
    }
    if (path.endsWith('/inventory')) {
      if (mode === 'forbidden') return fulfill(route, { error: { code: 'forbidden', message: 'Inventory access is required.' } }, 403)
      if (mode === 'error') return fulfill(route, { error: { code: 'temporarily_unavailable', message: 'The inventory service is temporarily unavailable.' } }, 503)
      return fulfill(route, inventoryPayload(companyId, url, mode))
    }
    const detail = path.match(/\/products\/(\d+)\/inventory-detail$/)
    if (detail) return fulfill(route, detailPayload(companyId, Number(detail[1])))
    if (path.endsWith('/search/products')) {
      return fulfill(route, {
        schema_version: 1, query: url.searchParams.get('q') ?? '', limited: false,
        results: [{
          id: 1, template_id: 1, name: 'Brake Pad 0001', sku: 'BP-0001', reference: 'OEM-BP-1',
          category: 'Brakes', supplier_names: ['Northline Auto Supply'],
        }],
      })
    }
    return fulfill(route, { error: { code: 'not_found', message: 'Unknown test endpoint.' } }, 404)
  })
}

async function expectNoOverflow(page: Page, width: number) {
  const dimensions = await page.evaluate(() => ({
    viewport: innerWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }))
  expect(dimensions.viewport).toBe(width)
  expect(dimensions.document).toBeLessThanOrEqual(width)
  expect(dimensions.body).toBeLessThanOrEqual(width)
}

test.beforeEach(async ({ page }) => installApi(page))

test('Inventory route, shared navigation, pagination, and responsive layouts use the server API', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/')
  await page.getByRole('button', { name: 'Inventory', exact: true }).click()
  await expect(page).toHaveURL(/\/inventory$/)
  await expect(page.getByRole('heading', { name: 'Inventory', level: 1 })).toBeVisible()
  await expect(page.getByText('1,001', { exact: true }).first()).toBeVisible()
  await expect(page.getByRole('row', { name: /Brake Pad 0001/ })).toBeVisible()
  await page.getByRole('button', { name: 'Next page' }).click()
  await expect(page.getByRole('row', { name: /Brake Pad 0026/ })).toBeVisible()
  expect(requests.get(page)?.some((url) => new URL(url).searchParams.get('page') === '2')).toBe(true)
  await page.getByRole('button', { name: 'Dashboard', exact: true }).click()
  await expect(page).toHaveURL('/')
  await page.goBack()
  await expect(page).toHaveURL(/\/inventory$/)
  await expect(page.getByRole('heading', { name: 'Inventory', level: 1 })).toBeVisible()

  for (const viewport of [{ width: 1440, height: 1000 }, { width: 1024, height: 800 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport)
    await expectNoOverflow(page, viewport.width)
    if (viewport.width === 390) {
      await expect(page.locator('.inventory-mobile-card')).toHaveCount(25)
      await expect(page.locator('.inventory-table-wrap')).toBeHidden()
    }
  }
})

test('search and filters are sent to Odoo before server pagination', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/inventory')
  const search = page.getByRole('searchbox', { name: 'Search by part name, SKU, OEM reference, or supplier' })
  await search.fill('BP-1001')
  await expect(page.getByRole('row', { name: /Brake Pad 1001/ })).toBeVisible()
  await expect.poll(() => requests.get(page)?.some((url) => {
    const parsed = new URL(url)
    return parsed.pathname.endsWith('/inventory') && parsed.searchParams.get('q') === 'BP-1001'
  })).toBe(true)

  await page.getByRole('combobox', { name: 'Filter by stock status' }).selectOption('low_stock')
  await page.getByRole('combobox', { name: 'Filter by warehouse' }).selectOption('10')
  await page.getByRole('combobox', { name: 'Filter by category' }).selectOption('2')
  await page.getByRole('combobox', { name: 'Filter by AutoStock monitoring' }).selectOption('tracked')
  await page.getByRole('combobox', { name: 'Filter by active or archived parts' }).selectOption('all')
  await page.getByRole('combobox', { name: 'Sort parts by' }).selectOption('sku')
  await page.getByRole('button', { name: 'Sort sku descending' }).click()
  await page.getByRole('combobox', { name: 'Supplier' }).fill('Northline Auto Supply')
  await expect.poll(() => {
    const pageRequest = requests.get(page)?.map((url) => new URL(url)).find((url) =>
      url.pathname.endsWith('/inventory') && url.searchParams.get('supplier_q') === 'Northline Auto Supply',
    )
    return pageRequest?.searchParams.get('status') === 'low_stock'
      && pageRequest?.searchParams.get('warehouse_id') === '10'
      && pageRequest?.searchParams.get('category_id') === '2'
      && pageRequest?.searchParams.get('tracked') === 'tracked'
      && pageRequest?.searchParams.get('active') === 'all'
      && pageRequest?.searchParams.get('sort') === 'sku'
      && pageRequest?.searchParams.get('direction') === 'desc'
  }).toBe(true)
})

test('product detail presents company stock, warehouse quantities, supplier terms, forecast, and plain-language movements', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 800 })
  await page.goto('/inventory')
  await page.getByRole('button', { name: 'Open details for Brake Pad 0001' }).click()
  const drawer = page.getByRole('dialog', { name: /Brake Pad 0001/ })
  await expect(drawer).toBeVisible()
  await expect(drawer.getByRole('heading', { name: 'Company-wide stock' })).toBeVisible()
  await expect(drawer.getByText('Stock by warehouse')).toBeVisible()
  await expect(drawer).toContainText('Northline Auto Supply')
  await expect(drawer).toContainText('Reviewed delivery forecast available')
  await expect(drawer).toContainText('Received')
  await expect(drawer).toContainText('PO/2026/088')
  await expect(drawer.getByRole('button', { name: /Create purchase|Adjust stock|Receive/ })).toHaveCount(0)
  await expect(drawer.locator('.inventory-detail-metrics')).toHaveCSS('display', 'grid')
  await expect(drawer.locator('.inventory-detail-metric').first()).toHaveCSS('border-top-style', 'solid')
  const metricColumns = await drawer.locator('.inventory-detail-metrics').evaluate((element) => getComputedStyle(element).gridTemplateColumns.split(' ').length)
  expect(metricColumns).toBe(2)
  await expect(drawer.locator('.inventory-warehouse-card').first()).toHaveCSS('border-top-style', 'solid')
  await expectNoOverflow(page, 1024)
})

test('global keyboard search opens the product detail on desktop and mobile', async ({ page }) => {
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 844 })
    await page.goto('/inventory')
    await expect(page.getByRole('heading', { name: 'Inventory', level: 1 })).toBeVisible()
    await page.keyboard.press('Control+k')
    const dialog = page.getByRole('dialog', { name: 'Search AutoStock' })
    await expect(dialog).toBeVisible()
    await dialog.getByRole('combobox', { name: 'Search parts, SKUs, suppliers, and references' }).fill('BP-0001')
    await expect(dialog.getByRole('option', { name: /Brake Pad 0001/ })).toBeVisible()
    await page.keyboard.press('Enter')
    await expect(page.getByRole('dialog', { name: /Brake Pad 0001/ })).toBeVisible()
    await page.keyboard.press('Escape')
    await expectNoOverflow(page, width)
  }
})

test('empty catalog, no results, permission, and service errors have useful states', async ({ page }) => {
  modes.set(page, 'empty')
  await page.goto('/inventory')
  await expect(page.getByRole('heading', { name: 'Your inventory is ready for its first parts' })).toBeVisible()

  modes.set(page, 'no-results')
  await page.reload()
  await expect(page.getByRole('heading', { name: 'No parts match these filters' })).toBeVisible()

  modes.set(page, 'forbidden')
  await page.reload()
  await expect(page.getByRole('alert')).toContainText('Inventory access is restricted')

  modes.set(page, 'error')
  await page.reload()
  await expect(page.getByRole('alert')).toContainText('could not be loaded')
  await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible()
})

test('mobile navigation can switch back to Dashboard and the Inventory list has no page overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/inventory')
  await page.getByRole('button', { name: 'Open navigation menu' }).click()
  const navigation = page.getByRole('dialog', { name: 'AutoStock navigation' })
  await expect(navigation).toBeVisible()
  await navigation.getByRole('button', { name: 'Dashboard', exact: true }).click()
  await expect(page).toHaveURL('/')
  await expect(page.getByRole('heading', { name: 'Dashboard', level: 1 })).toBeVisible()
  await page.getByRole('button', { name: 'Open navigation menu' }).click()
  await page.getByRole('dialog', { name: 'AutoStock navigation' }).getByRole('button', { name: 'Inventory', exact: true }).click()
  await expect(page).toHaveURL(/\/inventory$/)
  await expectNoOverflow(page, 390)
})
