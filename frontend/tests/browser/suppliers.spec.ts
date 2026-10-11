import { expect, test, type Page } from '@playwright/test'

const company = {
  id: 1, name: 'Atlas Auto Distribution', logo_url: '',
  currency: { code: 'MAD', symbol: 'DH', decimal_places: 2 },
  demo_environment: true, demo_environment_note: 'Fictional demonstration company.',
}

function session() {
  return {
    schema_version: 1, authenticated: true,
    user: { id: 7, name: 'Atlas Stock Manager', locale: 'en_US', timezone: 'Africa/Casablanca', permissions: { inventory: true, sales: true, inventory_manager: false } },
    current_company: company, allowed_companies: [company],
  }
}

function supplierRow(id: number, name = `Supplier ${id}`) {
  return {
    id, name, vendor_code: `V-${String(id).padStart(3, '0')}`, company_name: false,
    email: 'orders@example.invalid', phone: '+212 5 00 00 00 00', city: 'Casablanca', country: 'Morocco', partner_company: false,
    active: true, active_parts: 12 + id, tracked_parts: 9 + id, low_or_out_parts: id % 3,
    reorder_parts: id === 1 ? 2 : 0, reorder_locations: id === 1 ? 3 : 0, active_terms: 18 + id,
    has_active_terms: true, active_terms_status: 'has_terms', has_configured_terms: true,
    configured_terms_status: 'has_terms', lead_time_min_days: 6, lead_time_max_days: 14,
    attention: id === 1,
  }
}

function supplierPage(url: URL) {
  const query = url.searchParams.get('q') ?? ''
  const page = Number(url.searchParams.get('page') ?? 1)
  const attention = url.searchParams.get('attention') ?? 'all'
  const terms = url.searchParams.get('terms') ?? 'all'
  const sort = url.searchParams.get('sort') ?? 'name'
  const direction = url.searchParams.get('direction') ?? 'asc'
  const rows = Array.from({ length: 13 }, (_, index) => supplierRow(index + 1, index === 0 ? 'Northline Auto Supply' : `Supplier ${String(index + 1).padStart(2, '0')}`))
    .filter((row) => (!query || row.name.toLowerCase().includes(query.toLowerCase()) || row.vendor_code?.toLowerCase().includes(query.toLowerCase()))
      && (attention !== 'reorder' || Boolean(row.reorder_parts))
      && (terms !== 'none' || !row.has_active_terms)
      && (terms !== 'active' || row.has_active_terms))
    .sort((a, b) => {
      const result = sort === 'reorder' ? Number(b.reorder_parts) - Number(a.reorder_parts)
        : sort === 'parts' ? Number(b.active_parts) - Number(a.active_parts)
          : sort === 'lead_time' ? Number(a.lead_time_min_days) - Number(b.lead_time_min_days)
            : a.name.localeCompare(b.name)
      return direction === 'desc' ? -result : result
    })
  const selected = rows.slice((page - 1) * 12, page * 12)
  return {
    schema_version: 1, company, as_of: '2026-10-10 14:00:00',
    summary: { active_suppliers: 13, parts_with_supplier: 146, parts_missing_supplier: 29, suppliers_with_reorder_needs: 1 },
    filters: { query, attention, terms, sort, direction },
    suppliers: selected,
    pagination: { page, page_size: 12, total_count: rows.length, total_pages: Math.ceil(rows.length / 12), has_previous: page > 1, has_next: page < Math.ceil(rows.length / 12) },
    coverage: { supplier_terms_complete: true, product_catalog_complete: true, stock_complete: true, reorder_complete: true, supplier_limit: 5000, term_scan_limit: 100000, product_scan_limit: 50000, reorder_scan_limit: 5000, note: false },
    read_only: true,
  }
}

function part(id = 1001) {
  return {
    product_id: id, template_id: id, name: 'Alternator Assembly', sku: 'ALT-1001', reference: 'OEM-ALT-44',
    category_id: 4, category: 'Electrical', tracked: true, active: true, uom: 'Units', status: 'low_stock',
    on_hand: 2, available: 1, reserved: 1, incoming: 4, outgoing: 1, projected: 5, warehouse_count: 1,
    warehouses: [{ id: 10, name: 'Central Parts Warehouse', on_hand: 2, available: 1, reserved: 1, incoming: 4, outgoing: 1 }],
    supplier: { id: 21, name: 'Northline Auto Supply', lead_time_days: 8, lead_time_label: 'Supplier lead time', minimum_order_qty: 4, minimum_order_uom: 'Units', company_specific: true },
    supplier_access_note: false, supplier_lookup_limited: false, lead_time_days: 8, lead_time_label: 'Supplier lead time', lead_time_source: 'supplier',
    supplier_terms_count: 2, lead_time_min_days: 8, lead_time_max_days: 14,
    reorder_locations: [{ warehouse_id: 10, warehouse: 'Central Parts Warehouse', quantity: 6, uom: 'Units' }], reorder_parts: true,
  }
}

function partsPage(url: URL) {
  const query = url.searchParams.get('q') ?? ''
  const empty = Boolean(query && !'alternator assembly alt-1001 oem-alt-44'.includes(query.toLowerCase()))
  const rows = empty ? [] : [part()]
  return {
    schema_version: 1, company, as_of: '2026-10-10 14:00:00',
    summary: { total_tracked: 64, in_stock: 40, low_stock: 16, out_of_stock: 8, complete: true, sampled_products: 64, total_catalog: 146 },
    filters: { query, supplier_query: '', status: url.searchParams.get('status') ?? 'all', warehouse_id: false, category_id: false, supplier_id: false, tracked: 'all', active: 'active', sort: 'name', direction: 'asc' },
    items: rows,
    pagination: { page: Number(url.searchParams.get('page') ?? 1), page_size: 25, total_count: empty ? 0 : 1, total_pages: empty ? 0 : 1, has_previous: false, has_next: false, summary_exact: true, status_scan_used: false },
    coverage: { tracked_summary_complete: true, warehouse_scope_limited: false, supplier_lines_limited: false, supplier_terms_available: true, status_filter_complete: true, supplier_terms_complete: true, reorder_complete: true },
    empty_catalog: false,
  }
}

function terms() {
  return {
    schema_version: 1, company,
    product: { id: 1001, name: 'Alternator Assembly', sku: 'ALT-1001' },
    supplier: { id: 21, name: 'Northline Auto Supply' },
    terms: [
      { id: 71, sequence: 1, vendor_product_name: 'Alternateur 12V', vendor_product_code: 'NL-ALT-1', price: 1450, price_available: true, currency: { code: 'MAD', symbol: 'DH', decimal_places: 2 }, price_break_min_qty: 1, price_break_uom: 'Units', minimum_order_qty: 4, minimum_order_uom: 'Units', lead_time_days: 8, company_id: 1, company_name: company.name, valid_from: false, valid_until: false, active_today: true, variant_specific: false },
      { id: 72, sequence: 2, vendor_product_name: false, vendor_product_code: 'NL-ALT-10', price: 129, price_available: true, currency: { code: 'USD', symbol: '$', decimal_places: 2 }, price_break_min_qty: 10, price_break_uom: 'Units', minimum_order_qty: 4, minimum_order_uom: 'Units', lead_time_days: 14, company_id: false, company_name: false, valid_from: false, valid_until: false, active_today: true, variant_specific: true },
    ],
    terms_truncated: false, read_only: true,
  }
}

async function installCommon(page: Page) {
  await page.route('**/autostock/api/v1/session*', (route) => route.fulfill({ json: session() }))
}

test('Suppliers search, filters, pagination, and navigation stay readable without horizontal overflow', async ({ page }) => {
  await installCommon(page)
  const requests: URL[] = []
  await page.route('**/autostock/api/v1/suppliers?**', async (route) => {
    requests.push(new URL(route.request().url()))
    await route.fulfill({ json: supplierPage(new URL(route.request().url())) })
  })
  for (const [width, height] of [[1440, 1000], [1024, 900], [390, 844]]) {
    await page.setViewportSize({ width, height })
    await page.goto('/suppliers')
    await expect(page.getByRole('heading', { name: 'Suppliers', exact: true })).toBeVisible()
    await expect(page.getByText('146', { exact: true })).toBeVisible()
    await expect(page.getByRole('link', { name: /Northline Auto Supply/ }).first()).toBeVisible()
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
    expect(overflow).toBe(false)
  }
  await page.setViewportSize({ width: 1440, height: 1000 })
  await expect(page.getByRole('columnheader', { name: 'Low / out of stock' })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: 'Parts to restock' })).toBeVisible()
  await expect(page.locator('.supplier-filters label').filter({ hasText: 'Supplier terms' })).toBeVisible()
  await expect(page.getByRole('combobox', { name: 'Sort suppliers by' }).locator('option[value="reorder"]')).toHaveText('Parts to restock')
  await page.getByRole('searchbox', { name: 'Search suppliers by name or vendor code' }).fill('V-001')
  await expect.poll(() => requests.some((request) => request.searchParams.get('q') === 'V-001')).toBe(true)
  await expect(page.getByRole('link', { name: /Northline Auto Supply/ }).first()).toBeVisible()
  await expect(page.locator('.supplier-summary-grid .inventory-summary-card').filter({ hasText: 'Active suppliers' }).locator('strong')).toHaveText('13')
  await page.getByRole('combobox', { name: 'Filter suppliers by parts to restock' }).selectOption('reorder')
  await expect.poll(() => requests.some((request) => request.searchParams.get('attention') === 'reorder')).toBe(true)
  await page.getByRole('searchbox', { name: 'Search suppliers by name or vendor code' }).fill('')
  await expect.poll(() => requests.some((request) => !request.searchParams.get('q'))).toBe(true)
  await page.getByRole('combobox', { name: 'Filter suppliers by parts to restock' }).selectOption('all')
  await expect.poll(() => requests.some((request) => request.searchParams.get('attention') === 'all')).toBe(true)
  await page.getByRole('button', { name: 'Next page' }).click()
  await expect.poll(() => requests.some((request) => request.searchParams.get('page') === '2')).toBe(true)
  await page.getByRole('button', { name: 'Previous page' }).click()
  await page.getByRole('link', { name: /Northline Auto Supply/ }).first().click()
  await expect(page).toHaveURL(/\/suppliers\/\d+/)
})

test('supplier detail explains restock context and preserves every currency and quantity tier', async ({ page }) => {
  await installCommon(page)
  await page.route((url) => url.pathname === '/autostock/api/v1/suppliers/21', (route) => route.fulfill({ json: {
    schema_version: 1, company,
    supplier: { id: 21, name: 'Northline Auto Supply', vendor_code: 'NORTH', company_name: false, email: 'orders@example.invalid', phone: '+212 5 00 00 00 00', city: 'Casablanca', country: 'Morocco', partner_company: false },
    summary: { ...supplierRow(21, 'Northline Auto Supply'), reorder_parts: 2, reorder_locations: 3, attention: true },
    purchase_history: { available: false, note: 'Purchase order history is not available in this setup. Supplier terms and stock details are still available.', items: [] },
    coverage: { supplier_terms_complete: true, stock_complete: true, reorder_complete: true, reorder_scanned: 2, reorder_candidates: 2 },
    as_of: '2026-10-10 14:00:00', read_only: true,
  } }))
  await page.route('**/autostock/api/v1/suppliers/21/parts?**', (route) => route.fulfill({ json: partsPage(new URL(route.request().url())) }))
  await page.route('**/autostock/api/v1/suppliers/21/parts/1001/terms*', (route) => route.fulfill({ json: terms() }))
  await page.goto('/suppliers/21')
  await expect(page.getByRole('heading', { name: 'Northline Auto Supply', exact: true })).toBeVisible()
  await expect(page.getByText(/Purchase order history is not available in this setup/)).toBeVisible()
  await expect(page.getByRole('columnheader', { name: 'Suggested order' })).toBeVisible()
  await expect(page.locator('.supplier-detail-metrics .inventory-summary-copy').filter({ hasText: 'Parts to restock' })).toBeVisible()
  await expect(page.getByText(/Central Parts Warehouse: 6 Units suggested/).first()).toBeVisible()
  for (const [width, height] of [[1440, 1000], [1024, 900], [390, 844]]) {
    await page.setViewportSize({ width, height })
    expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  }
  await expect(page.locator('.supplier-part-mobile-list').filter({ hasText: 'Central Parts Warehouse: 6 Units suggested' })).toBeVisible()
  await page.getByRole('button', { name: /View terms/ }).first().click()
  await expect(page.getByText('DH 1,450.00 MAD')).toBeVisible()
  await expect(page.getByText('$ 129.00 USD')).toBeVisible()
  await expect(page.getByText('Price applies from').first()).toBeVisible()
  await expect(page.getByText('10 Units')).toBeVisible()
  await expect(page.getByText('Minimum order').first()).toBeVisible()
  await expect(page.getByText('4 Units').first()).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
})

test('Parts without a supplier is a truthful, searchable, paged view', async ({ page }) => {
  await installCommon(page)
  const requests: URL[] = []
  await page.route('**/autostock/api/v1/supplier-gaps?**', async (route) => {
    requests.push(new URL(route.request().url()))
    const result = partsPage(new URL(route.request().url()))
    if (result.items[0]) result.items[0].supplier = false
    await route.fulfill({ json: result })
  })
  await page.goto('/suppliers/missing')
  await expect(page.getByRole('heading', { name: 'Parts without a supplier', exact: true })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: 'Suggested order' })).toBeVisible()
  await expect(page.getByText(/Central Parts Warehouse: 6 Units suggested/).first()).toBeVisible()
  await expect(page.getByText('No supplier on file', { exact: true }).first()).toBeVisible()
  await page.getByRole('searchbox', { name: 'Search parts without a supplier' }).fill('ALT-1001')
  await expect.poll(() => requests.some((request) => request.searchParams.get('q') === 'ALT-1001')).toBe(true)
  await expect(page.getByText('Alternator Assembly', { exact: true }).first()).toBeVisible()
  for (const [width, height] of [[1440, 900], [1024, 850], [390, 844]]) {
    await page.setViewportSize({ width, height })
    await expect(page.getByRole('heading', { name: 'Parts without a supplier', exact: true })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  }
})

test('supplier screens show useful no-results and permission states', async ({ page }) => {
  await installCommon(page)
  await page.route('**/autostock/api/v1/suppliers?**', (route) => {
    const url = new URL(route.request().url())
    if (url.searchParams.get('q') === 'unknown') return route.fulfill({ json: { ...supplierPage(url), suppliers: [], pagination: { page: 1, page_size: 12, total_count: 0, total_pages: 0, has_previous: false, has_next: false } } })
    return route.fulfill({ json: supplierPage(url) })
  })
  await page.goto('/suppliers')
  await page.getByRole('searchbox', { name: 'Search suppliers by name or vendor code' }).fill('unknown')
  await expect(page.getByRole('heading', { name: 'No suppliers match these filters' })).toBeVisible()
  await page.unroute('**/autostock/api/v1/suppliers?**')
  await page.route('**/autostock/api/v1/suppliers?**', (route) => route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ error: { code: 'forbidden', message: 'Inventory access is required to view supplier and stock information.' } }) }))
  await page.goto('/suppliers')
  await expect(page.getByRole('heading', { name: 'Supplier information is restricted' })).toBeVisible()
})
