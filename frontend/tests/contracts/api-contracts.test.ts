import { describe, expect, it } from 'vitest'
import { dashboardSchema, forecastSchema, restockSchema, sessionSchema } from '../../src/api/contracts'

const company = {
  id: 1,
  name: 'Fixture Auto Parts',
  logo_url: '/web/image/res.company/1/logo_web',
  currency: { code: 'MAD', symbol: 'DH', decimal_places: 2 },
  demo_environment: true,
  demo_environment_note: 'Fictional demonstration data.',
}

describe('Odoo v1 API contracts', () => {
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
})
