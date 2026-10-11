import { describe, expect, it } from 'vitest'
import {
  dashboardSchema, forecastSchema, inventoryDetailSchema, inventorySchema,
  forecastDetailSchema, forecastsSchema, restockSchema, sessionSchema, supplierDetailSchema, supplierGapsSchema,
  supplierTermsSchema, suppliersSchema, warehouseDetailSchema, warehousesSchema,
} from '../../src/api/contracts'

const company = {
  id: 1,
  name: 'Fixture Auto Parts',
  logo_url: '/web/image/res.company/1/logo_web',
  currency: { code: 'MAD', symbol: 'DH', decimal_places: 2 },
  demo_environment: true,
  demo_environment_note: 'Fictional demonstration data.',
}

describe('Odoo v1 API contracts', () => {
  it('accepts exact server forecast counts and a bounded filtered page', () => {
    const parsed = forecastsSchema.safeParse({
      schema_version: 1, company,
      filters: { query: 'ALT-1001', warehouse_id: 8, horizon_days: 30, state: 'completed', review_status: 'unreviewed', source_type: 'completed_deliveries' },
      runs: [{
        id: 201, product_id: 1001, product_name: 'Alternator Assembly', sku: 'ALT-1001',
        warehouse_id: 8, warehouse_name: 'Central Parts Warehouse', horizon_days: 30,
        history_start: '2026-01-01', history_end: '2026-06-29', source_cutoff: '2026-06-30 12:00:00',
        created_at: '2026-06-30 12:00:00', source_type: 'completed_deliveries', state: 'completed',
        evaluation_status: 'evaluated', review_status: 'unreviewed',
      }],
      pagination: { page: 41, page_size: 25, total_count: 1001, total_pages: 41, has_previous: true, has_next: false },
      warehouse_options: [{ id: 8, name: 'Central Parts Warehouse' }],
      warehouse_options_limited: false, warehouse_count: 1, real_history_access: true, access_note: false, read_only: true,
    })
    expect(parsed.success).toBe(true)
    if (parsed.success) {
      expect(parsed.data.pagination.total_count).toBe(1001)
      expect(parsed.data.runs[0].review_status).toBe('unreviewed')
    }
  })

  it('keeps exact-run history, returns, forecast points, and restock eligibility in one read-only detail contract', () => {
    const parsed = forecastDetailSchema.safeParse({
      schema_version: 1, company,
      run: {
        id: 201, name: 'ALT-1001 · 7 days', company_id: 1, company_name: company.name,
        product_id: 1001, warehouse_id: 8, warehouse_name: 'Central Parts Warehouse', uom: 'Units',
        created_at: '2026-06-30 12:00:00', state: 'completed', evaluation_status: 'evaluated', failure_reason: false,
        source_type: 'completed_deliveries', source_label: 'Completed deliveries, with returns recorded separately',
        sku: 'ALT-1001', product_name: 'Alternator Assembly', horizon_days: 7,
        history_start: '2026-01-01', history_end: '2026-06-29', source_cutoff: '2026-06-30 12:00:00', source_timezone: 'UTC',
        history_days: 180, nonzero_days: 12, source_event_count: 84, source_snapshot_sha256: 'abc', model_version: 'test',
        selected_method: 'trailing_mean', baseline_method: 'seasonal_naive', demand_pattern: 'regular', evaluation_days: 7,
        baseline_mae: 1.2, ml_mae: 0.9, ml_evaluated: true, review_status: 'unreviewed', reviewed_by: false, reviewed_at: false,
        data_provenance: 'Completed deliveries in Odoo.', assumptions: 'Fulfilled sales proxy.', limitations: 'Stockouts can censor demand.', interval_note: 'Heuristic range.',
        current_stock: { on_hand: 4, odoo_projected: 6, uom: 'Units' },
        observations: [{ day: '2026-06-29', delivered_units: 2, returned_units: 1, units: 2, source_event_count: 3 }],
        predictions: [{ day: '2026-06-30', units: 2.5, lower_heuristic: 1, upper_heuristic: 4 }],
      },
      history_coverage: { configured: true, complete_from: '2026-01-01', run_starts_within_coverage: true },
      restock_guidance: { status: 'not_eligible', usable: false, reason: 'This forecast has not been reviewed.' },
      read_only: true,
    })
    expect(parsed.success).toBe(true)
    if (parsed.success) {
      expect(parsed.data.run.observations[0].returned_units).toBe(1)
      expect(parsed.data.restock_guidance.usable).toBe(false)
    }
  })

  it('accepts a session with explicit allowed companies and permissions', () => {
    const parsed = sessionSchema.safeParse({
      schema_version: 1,
      authenticated: true,
      user: { id: 3, name: 'Demo Operator', locale: 'en_US', timezone: 'UTC', permissions: { inventory: true, sales: true, inventory_manager: false } },
      current_company: company,
      allowed_companies: [company],
    })
    expect(parsed.success).toBe(true)
  })

  it('keeps supplier summaries honest when a catalog scan is incomplete', () => {
    const parsed = suppliersSchema.safeParse({
      schema_version: 1, company, as_of: '2026-10-10 12:00:00',
      summary: { active_suppliers: 2, parts_with_supplier: false, parts_missing_supplier: false, suppliers_with_reorder_needs: false },
      filters: { query: '', attention: 'all', terms: 'all', sort: 'name', direction: 'asc' },
      suppliers: [{
        id: 7, name: 'Northline Auto Supply', vendor_code: 'NORTH', company_name: false,
        email: 'orders@example.invalid', phone: false, city: 'Rabat', country: 'Morocco', partner_company: false,
        active: true, active_parts: false, tracked_parts: false, low_or_out_parts: false,
        reorder_parts: false, reorder_locations: false, active_terms: false,
        has_active_terms: false, active_terms_status: 'unknown', has_configured_terms: false,
        configured_terms_status: 'unknown', lead_time_min_days: false, lead_time_max_days: false, attention: false,
      }],
      pagination: { page: 1, page_size: 12, total_count: 1, total_pages: 1, has_previous: false, has_next: false },
      coverage: { supplier_terms_complete: false, product_catalog_complete: true, stock_complete: false, reorder_complete: false, supplier_limit: 5000, term_scan_limit: 100000, product_scan_limit: 50000, reorder_scan_limit: 5000, note: 'Supplier summary is incomplete.' },
      read_only: true,
    })
    expect(parsed.success).toBe(true)
    if (parsed.success) {
      expect(parsed.data.summary.parts_missing_supplier).toBe(false)
      expect(parsed.data.suppliers[0].active_terms_status).toBe('unknown')
    }
  })

  it('preserves vendor price tiers, currency, MOQ, and lead time as separate terms', () => {
    const parsed = supplierTermsSchema.safeParse({
      schema_version: 1, company,
      product: { id: 1001, name: 'Alternator Assembly', sku: 'ALT-1001' },
      supplier: { id: 7, name: 'Northline Auto Supply' },
      terms: [
        { id: 12, sequence: 1, vendor_product_name: 'Alternator', vendor_product_code: 'N-ALT', price: 145, price_available: true, currency: { code: 'MAD', symbol: 'DH', decimal_places: 2 }, price_break_min_qty: 1, price_break_uom: 'Units', minimum_order_qty: 4, minimum_order_uom: 'Units', lead_time_days: 12, company_id: 1, company_name: company.name, valid_from: false, valid_until: false, active_today: true, variant_specific: false },
        { id: 13, sequence: 2, vendor_product_name: false, vendor_product_code: false, price: 132, price_available: true, currency: { code: 'USD', symbol: '$', decimal_places: 2 }, price_break_min_qty: 10, price_break_uom: 'Units', minimum_order_qty: 4, minimum_order_uom: 'Units', lead_time_days: 14, company_id: false, company_name: false, valid_from: false, valid_until: false, active_today: true, variant_specific: true },
      ],
      terms_truncated: false,
      read_only: true,
    })
    expect(parsed.success).toBe(true)
    if (parsed.success) {
      expect(parsed.data.terms).toHaveLength(2)
      expect(parsed.data.terms.map((term) => term.currency.code)).toEqual(['MAD', 'USD'])
      expect(parsed.data.terms.map((term) => term.price_break_min_qty)).toEqual([1, 10])
      expect(parsed.data.terms[0].minimum_order_qty).toBe(4)
    }
  })

  it('requires the supplier detail to say when purchase history is unavailable', () => {
    const baseSupplier = {
      id: 7, name: 'Northline Auto Supply', vendor_code: false, company_name: false,
      email: false, phone: false, city: false, country: false, partner_company: false,
    }
    const supplierRow = {
      ...baseSupplier, active: true, active_parts: 4, tracked_parts: 3, low_or_out_parts: 1,
      reorder_parts: 1, reorder_locations: 1, active_terms: 5, has_active_terms: true,
      active_terms_status: 'has_terms', has_configured_terms: true, configured_terms_status: 'has_terms',
      lead_time_min_days: 5, lead_time_max_days: 14, attention: true,
    }
    const parsed = supplierDetailSchema.safeParse({
      schema_version: 1, company, supplier: baseSupplier, summary: supplierRow,
      purchase_history: { available: false, note: 'Purchase history is not available in this setup.', items: [] },
      coverage: { supplier_terms_complete: true, stock_complete: true, reorder_complete: true, reorder_scanned: 2, reorder_candidates: 2 },
      as_of: '2026-10-10 12:00:00', read_only: true,
    })
    expect(parsed.success).toBe(true)
    if (parsed.success) expect(parsed.data.purchase_history.available).toBe(false)
  })

  it('requires missing-supplier results to retain the server inventory contract', () => {
    const parsed = supplierGapsSchema.safeParse({
      schema_version: 1, company, as_of: '2026-10-10 12:00:00',
      summary: { total_tracked: 2, in_stock: 1, low_stock: 1, out_of_stock: 0, complete: true, sampled_products: 2, total_catalog: 4 },
      filters: { query: '', supplier_query: '', status: 'all', warehouse_id: false, category_id: false, supplier_id: false, tracked: 'all', active: 'active', sort: 'name', direction: 'asc' },
      items: [], pagination: { page: 1, page_size: 25, total_count: 0, total_pages: 0, has_previous: false, has_next: false, summary_exact: true, status_scan_used: false },
      coverage: { tracked_summary_complete: true, warehouse_scope_limited: false, supplier_lines_limited: false, supplier_terms_available: true, status_filter_complete: true, supplier_terms_complete: true, reorder_complete: true },
      empty_catalog: false,
    })
    expect(parsed.success).toBe(true)
  })

  it('rejects dashboard responses missing sample coverage disclosure', () => {
    const parsed = dashboardSchema.safeParse({
      schema_version: 1,
      company,
      snapshot_at: '2026-10-10 12:00 UTC',
      kpis: { tracked_products: 64, in_stock: 40, low_stock: 16, out_of_stock: 8 },
      inventory_health: { total_tracked: 64, sampled_products: 64, categories: [] },
      empty: false,
    })
    expect(parsed.success).toBe(false)
  })

  it('requires restock previews to stay read-only and bounded', () => {
    const parsed = restockSchema.safeParse({
      schema_version: 1,
      company,
      warehouse_id: false,
      warehouses: [],
      as_of: '2026-10-10 12:00 UTC',
      read_only: true,
      summary: { priority_locations: 6, reorder_suggestions: 6, complete: true },
      items: Array.from({ length: 6 }, (_, index) => ({
        key: `part-${index}`, product_id: index + 1, template_id: index + 1, name: 'Test part', sku: 'T-1',
        warehouse_id: 1, warehouse: 'Test warehouse', status: 'low', status_label: 'Low stock', current_qty: 1,
        uom: 'Units', recommended_qty: 2, supplier_name: false, reason: 'Stock reached trigger', basis_note: 'Odoo rule',
      })),
      coverage: { complete: true, scanned_locations: 6, candidate_locations: 6, scan_limit: 500, flags: {} },
    })
    expect(parsed.success).toBe(false)
  })

  it('keeps a clean product name separate from its SKU in restock items', () => {
    const parsed = restockSchema.parse({
      schema_version: 1,
      company,
      warehouse_id: 1,
      warehouses: [{ id: 1, name: 'Central warehouse' }],
      as_of: '2026-10-10 12:00 UTC',
      read_only: true,
      summary: { priority_locations: 1, reorder_suggestions: 1, complete: true },
      items: [{
        key: 'part-1', product_id: 1, template_id: 1, name: 'Ignition Coil', sku: 'AT-01-003',
        reference: '', category: 'Ignition',
        warehouse_id: 1, warehouse: 'Central warehouse', status: 'out', status_label: 'Out of stock',
        current_qty: 0, free_qty: 0, reserved_qty: 0, incoming_qty: 0, outgoing_qty: 0,
        projected_qty: 0, projected_after_demand: 0, forecast_demand: false, forecast_used: false,
        forecast_reason: 'No reviewed forecast is available.', forecast_horizon_days: false,
        forecast_review_status: false, uom: 'Units', recommended_qty: 10, reorder_needed: true,
        supplier_name: 'Supplier', supplier: false, supplier_access_note: false,
        reason: 'No stock is on hand at this warehouse.', basis_note: 'Odoo restock policy.',
        lead_time_days: 0, lead_time_source: 'unavailable', lead_time_label: 'Not provided',
        minimum_threshold: false, target_stock: false, policy_source: 'none',
        policy_source_label: 'No reorder policy', policy_issue: 'Policy missing',
        calculation_basis: 'No reliable quantity calculated.',
      }],
      insights: [
        { id: 'reorder-suggestions', title: 'Reorder suggestions', description: '1 part location has a suggested order ready for review.', icon: 'reorder', action: 'view-reorder', action_label: 'View top 5' },
        { id: 'stock-review', title: 'Part locations to review', description: '1 part location needs review.', icon: 'trend', action: 'review-parts', action_label: 'Review parts' },
        { id: 'out-of-stock', title: 'Warehouse stockouts', description: '1 part location currently has zero stock.', icon: 'vehicle', action: 'view-reorder', action_label: 'View top 5' },
      ],
      coverage: { complete: true, scanned_locations: 1, candidate_locations: 1, scan_limit: 500, flags: {} },
    })
    expect(parsed.items[0]).toMatchObject({ name: 'Ignition Coil', sku: 'AT-01-003' })
    expect(parsed.items[0].name).not.toContain(parsed.items[0].sku)
  })

  it('distinguishes an unavailable forecast from a saved forecast', () => {
    const parsed = forecastSchema.safeParse({
      schema_version: 1,
      company,
      status: 'unavailable',
      reason_code: 'no_evaluated_forecast',
      message: 'No completed forecast is available.',
      options: [],
      options_limited: false,
      forecast: false,
    })
    expect(parsed.success).toBe(true)
  })

  it('accepts a server-paged inventory response whose total catalog exceeds one thousand parts', () => {
    const item = {
      product_id: 1001, template_id: 1001, name: 'Water Pump', sku: 'WP-1001', reference: 'OEM-001',
      category_id: 4, category: 'Cooling', tracked: true, active: true, uom: 'Units',
      status: 'low_stock', on_hand: 2, available: 1, reserved: 1, incoming: 4, outgoing: 1, projected: 5,
      warehouse_count: 1,
      warehouses: [{ id: 8, name: 'Central', on_hand: 2, available: 1, reserved: 1, incoming: 4, outgoing: 1 }],
      supplier: { id: 22, name: 'Northline Supply', lead_time_days: 12, lead_time_label: 'Supplier lead time', minimum_order_qty: 1, minimum_order_uom: 'Units', company_specific: true },
      supplier_access_note: false, supplier_lookup_limited: false, lead_time_days: 12,
      lead_time_label: 'Supplier lead time', lead_time_source: 'supplier',
    }
    const parsed = inventorySchema.safeParse({
      schema_version: 1, company, as_of: '2026-10-10 12:00:00',
      summary: { total_tracked: 320, in_stock: 250, low_stock: 48, out_of_stock: 22, complete: true, sampled_products: 320, total_catalog: 1001 },
      filters: { query: '', supplier_query: '', status: 'all', warehouse_id: false, category_id: false, supplier_id: false, tracked: 'all', active: 'active', sort: 'name', direction: 'asc' },
      items: [item],
      pagination: { page: 41, page_size: 25, total_count: 1001, total_pages: 41, has_previous: true, has_next: false, summary_exact: true, status_scan_used: false },
      coverage: { tracked_summary_complete: true, warehouse_scope_limited: false, supplier_lines_limited: false, supplier_terms_available: true, status_filter_complete: true },
      empty_catalog: false,
    })
    expect(parsed.success).toBe(true)
    if (parsed.success) {
      expect(parsed.data.items).toHaveLength(1)
      expect(parsed.data.items[0].product_id).toBe(1001)
      expect(parsed.data.pagination.total_count).toBe(1001)
      expect(parsed.data.pagination.page).toBe(41)
    }
  })

  it('requires product details to distinguish company stock, warehouse stock, supplier access, and movements', () => {
    const parsed = inventoryDetailSchema.safeParse({
      schema_version: 1, company,
      product: { id: 10, template_id: 10, name: 'Water Pump', sku: 'WP-10', reference: false, category_id: 4, category: 'Cooling', tracked: false, active: true, uom: 'Units', safety_stock: 0 },
      company_stock: { on_hand: 7, available: 5, reserved: 2, incoming: 3, outgoing: 1, projected: 9 },
      warehouses: [{ id: 8, name: 'Central', on_hand: 7, available: 5, reserved: 2, incoming: 3, outgoing: 1, selected: false, projected: 9 }],
      supplier: false, supplier_access: false, supplier_note: 'Supplier details are restricted.',
      lead_time_days: 0, lead_time_label: 'Planning assumption', lead_time_source: 'planning_assumption',
      forecast: { status: 'not_tracked', message: 'Monitoring is not enabled.', horizon_days: false, history_start: false, history_end: false, used_for_restock: false, demand_before_delivery: false },
      recommendations: [],
      recommendation_coverage: { complete: true, candidate_locations: 0, scanned_locations: 0, forecast_access_available: false, forecast_access_reason: false },
      movements_available: true, movements: [],
      movement_note: 'No stock changes were recorded in the last 90 days.',
      coverage: { warehouse_scope_limited: false, total_warehouses: 1, supplier_terms_available: false },
      read_only: true,
    })
    expect(parsed.success).toBe(true)
  })

  it('accepts warehouse summaries as part-position counts without summing mixed product units', () => {
    const row = {
      id: 8, name: 'Central Warehouse', code: 'CENT', company_name: company.name,
      catalog_parts: 1001, tracked_catalog_parts: 64, stocked_parts: 40, tracked_parts_present: 38,
      low_stock_parts: 16, out_of_stock_parts: 8, parts_with_reserved_stock: 12,
      parts_with_incoming_stock: 9, parts_with_outgoing_stock: 7,
      summary_complete: true, summary_note: false, status: 'needs_attention',
      recent_activity_at: '2026-10-10T14:00:00Z', activity_available: true,
    }
    const parsed = warehousesSchema.safeParse({
      schema_version: 1, company, as_of: '2026-10-10 12:00:00',
      summary: { active_warehouses: 2, warehouses_needing_attention: 1, warehouses_with_low_stock: 1, warehouses_with_stockouts: 1, warehouses_with_incoming: 1, complete: true },
      filters: { query: '', status: 'all', sort: 'attention', direction: 'desc' },
      warehouses: [row],
      pagination: { page: 1, page_size: 12, total_count: 2, total_pages: 1, has_previous: false, has_next: false },
      coverage: { summary_complete: true, catalog_product_count: 1001, catalog_scan_limit: 50000, warehouse_count: 2, warehouse_limit: 500, activity_available: true },
    })
    expect(parsed.success).toBe(true)
    if (parsed.success) {
      expect(parsed.data.warehouses[0].parts_with_reserved_stock).toBe(12)
      expect(parsed.data.warehouses[0].catalog_parts).toBe(1001)
    }
  })

  it('requires warehouse detail movements and part-specific inventory figures to stay explicit', () => {
    const parsed = warehouseDetailSchema.safeParse({
      schema_version: 1, company,
      warehouse: { id: 8, name: 'Central Warehouse', code: 'CENT', company_name: company.name },
      summary: {
        catalog_parts: 1001, tracked_catalog_parts: 64, stocked_parts: 40, tracked_parts_present: 38,
        low_stock_parts: 16, out_of_stock_parts: 8, parts_with_reserved_stock: 12,
        parts_with_incoming_stock: 9, parts_with_outgoing_stock: 7, summary_complete: true,
        summary_note: false, reorder_suggestions: 5, reorder_suggestions_complete: true, reorder_suggestions_note: false,
      },
      attention_parts: [{ product_id: 1001, name: 'Water Pump', sku: 'WP-1001', uom: 'Units', status: 'low_stock', on_hand: 2, available: 1 }],
      activity_available: true,
      activity: [{ id: 90, kind: 'received', label: 'Received', date: '2026-10-10T10:00:00Z', completed: true, product_id: 1001, product_name: 'Water Pump', sku: 'WP-1001', quantity: 6, uom: 'Units', reference: 'WH/IN/0090', counterpart_warehouse: false }],
      activity_note: 'Completed changes cover the last 90 days.', as_of: '2026-10-10 12:00:00', read_only: true,
    })
    expect(parsed.success).toBe(true)
  })
})
