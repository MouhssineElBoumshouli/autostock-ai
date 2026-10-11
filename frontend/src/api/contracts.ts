import { z } from 'zod'

const companySchema = z.object({
  id: z.number().int().positive(),
  name: z.string(),
  logo_url: z.string(),
  currency: z.object({ code: z.string(), symbol: z.string(), decimal_places: z.number() }),
  demo_environment: z.boolean(),
  demo_environment_note: z.union([z.string(), z.literal(false)]),
})

export const sessionSchema = z.object({
  schema_version: z.literal(1),
  authenticated: z.literal(true),
  user: z.object({
    id: z.number().int(),
    name: z.string(),
    locale: z.string(),
    timezone: z.string(),
    permissions: z.object({
      inventory: z.boolean(),
      sales: z.boolean(),
      inventory_manager: z.boolean(),
    }),
  }),
  current_company: companySchema,
  allowed_companies: z.array(companySchema),
})

export const dashboardSchema = z.object({
  schema_version: z.literal(1),
  company: companySchema,
  snapshot_at: z.string(),
  kpis: z.object({
    tracked_products: z.number().int().nonnegative(),
    in_stock: z.number().int().nonnegative(),
    low_stock: z.number().int().nonnegative(),
    out_of_stock: z.number().int().nonnegative(),
    reviewed_forecasts: z.union([z.number().int().nonnegative(), z.literal(false)]),
    reviewed_forecasts_available: z.boolean(),
  }),
  inventory_health: z.object({
    total_tracked: z.number().int().nonnegative(),
    sampled_products: z.number().int().nonnegative(),
    complete: z.boolean(),
    categories: z.array(z.object({
      key: z.enum(['healthy', 'low', 'out']),
      label: z.string(),
      count: z.number().int().nonnegative(),
      percent: z.number().int().min(0).max(100),
    })),
  }),
  empty: z.boolean(),
})

export const riskItemSchema = z.object({
  key: z.string(),
  product_id: z.number().int().positive(),
  template_id: z.number().int().positive(),
  name: z.string(),
  sku: z.string(),
  reference: z.string(),
  category: z.string(),
  warehouse_id: z.number().int().positive(),
  warehouse: z.string(),
  status: z.string(),
  status_label: z.string(),
  current_qty: z.number(),
  free_qty: z.number(),
  reserved_qty: z.number(),
  incoming_qty: z.number(),
  outgoing_qty: z.number(),
  projected_qty: z.number(),
  projected_after_demand: z.number(),
  forecast_demand: z.union([z.number(), z.literal(false)]),
  forecast_used: z.boolean(),
  forecast_reason: z.union([z.string(), z.literal(false)]),
  forecast_horizon_days: z.union([z.number().int().positive(), z.literal(false)]),
  forecast_review_status: z.union([z.string(), z.literal(false)]),
  uom: z.string(),
  recommended_qty: z.union([z.number(), z.literal(false)]),
  reorder_needed: z.boolean(),
  supplier_name: z.union([z.string(), z.literal(false)]),
  supplier: z.union([
    z.object({
      id: z.number().int().positive(),
      name: z.string(),
      lead_days: z.number().int().nonnegative(),
      minimum_qty: z.number().nonnegative(),
      minimum_uom: z.string(),
      price_tier_min_qty: z.number().nonnegative(),
      price_tier_uom: z.string(),
      price: z.number(),
      currency: z.string(),
      company_specific: z.boolean(),
    }),
    z.literal(false),
  ]),
  supplier_access_note: z.union([z.string(), z.literal(false)]),
  reason: z.string(),
  basis_note: z.string(),
  lead_time_days: z.number().int().nonnegative(),
  lead_time_source: z.string(),
  lead_time_label: z.string(),
  minimum_threshold: z.union([z.number(), z.literal(false)]),
  target_stock: z.union([z.number(), z.literal(false)]),
  policy_source: z.string(),
  policy_source_label: z.string(),
  policy_issue: z.union([z.string(), z.literal(false)]),
  calculation_basis: z.string(),
})

export const insightSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
  icon: z.enum(['trend', 'reorder', 'vehicle']),
  action: z.enum(['review-parts', 'view-reorder']),
  action_label: z.string(),
})

export const restockSchema = z.object({
  schema_version: z.literal(1),
  company: companySchema,
  warehouse_id: z.union([z.number().int().positive(), z.literal(false)]),
  warehouses: z.array(z.object({ id: z.number().int().positive(), name: z.string() })),
  as_of: z.string(),
  read_only: z.literal(true),
  summary: z.object({
    priority_locations: z.number().int().nonnegative(),
    reorder_suggestions: z.number().int().nonnegative(),
    complete: z.boolean(),
  }),
  items: z.array(riskItemSchema).max(5),
  insights: z.array(insightSchema).length(3),
  coverage: z.object({
    complete: z.boolean(),
    scanned_locations: z.number().int().nonnegative(),
    candidate_locations: z.number().int().nonnegative(),
    scan_limit: z.number().int().positive(),
    flags: z.record(z.string(), z.boolean()),
  }),
})

const forecastDataSchema = z.object({
  id: z.number().int().positive(),
  product_name: z.string(),
  sku: z.string(),
  warehouse_name: z.union([z.string(), z.literal(false)]),
  horizon_days: z.number().int().positive(),
  uom: z.string(),
  source_type: z.string(),
  source_label: z.string(),
  review_status: z.string(),
  evaluation_status: z.string(),
  history_start: z.string(),
  history_end: z.string(),
  history: z.array(z.object({ date: z.string(), units: z.number() })),
  predictions: z.array(z.object({
    date: z.string(), units: z.number(), lower: z.number(), upper: z.number(),
  })),
  limitations: z.string(),
})

const forecastOptionSchema = z.object({
  key: z.string(),
  product_id: z.number().int().positive(),
  name: z.string(),
  sku: z.string(),
  warehouse_id: z.union([z.number().int().positive(), z.literal(false)]),
  warehouse: z.union([z.string(), z.literal(false)]),
})

export const forecastSchema = z.discriminatedUnion('status', [
  z.object({
    schema_version: z.literal(1),
    company: companySchema,
    status: z.literal('available'),
    reason_code: z.literal(false),
    message: z.literal(false),
    options: z.array(forecastOptionSchema).max(100),
    options_limited: z.boolean(),
    forecast: forecastDataSchema,
  }),
  z.object({
    schema_version: z.literal(1),
    company: companySchema,
    status: z.enum(['unavailable', 'restricted']),
    reason_code: z.string(),
    message: z.string(),
    options: z.array(forecastOptionSchema).max(100),
    options_limited: z.boolean(),
    forecast: z.literal(false),
  }),
])

const forecastListRunSchema = z.object({
  id: z.number().int().positive(),
  product_id: z.union([z.number().int().positive(), z.literal(false)]),
  product_name: z.string(),
  sku: z.string(),
  warehouse_id: z.union([z.number().int().positive(), z.literal(false)]),
  warehouse_name: z.union([z.string(), z.literal(false)]),
  horizon_days: z.union([z.literal(7), z.literal(30), z.literal(60)]),
  history_start: z.string(),
  history_end: z.string(),
  source_cutoff: z.string(),
  created_at: z.string(),
  source_type: z.enum(['completed_deliveries', 'synthetic_demo']),
  state: z.enum(['queued', 'running', 'completed', 'insufficient_history', 'no_observed_demand', 'failed']),
  evaluation_status: z.union([z.string(), z.literal(false)]),
  review_status: z.enum(['unreviewed', 'reviewed']),
})

export const forecastsSchema = z.object({
  schema_version: z.literal(1),
  company: companySchema,
  filters: z.object({
    query: z.string(),
    warehouse_id: z.union([z.number().int().positive(), z.literal(false)]),
    horizon_days: z.union([z.literal('all'), z.literal(7), z.literal(30), z.literal(60)]),
    state: z.union([z.literal('all'), z.enum(['queued', 'running', 'completed', 'insufficient_history', 'no_observed_demand', 'failed'])]),
    review_status: z.union([z.literal('all'), z.enum(['unreviewed', 'reviewed'])]),
    source_type: z.union([z.literal('all'), z.enum(['completed_deliveries', 'synthetic_demo'])]),
  }),
  runs: z.array(forecastListRunSchema).max(50),
  pagination: z.object({
    page: z.number().int().positive(),
    page_size: z.number().int().positive().max(50),
    total_count: z.number().int().nonnegative(),
    total_pages: z.number().int().nonnegative(),
    has_previous: z.boolean(),
    has_next: z.boolean(),
  }),
  warehouse_options: z.array(z.object({ id: z.number().int().positive(), name: z.string() })).max(100),
  warehouse_options_limited: z.boolean(),
  warehouse_count: z.number().int().nonnegative(),
  real_history_access: z.boolean(),
  access_note: z.union([z.string(), z.literal(false)]),
  read_only: z.literal(true),
})

export const forecastDetailSchema = z.object({
  schema_version: z.literal(1),
  company: companySchema,
  run: z.object({
    id: z.number().int().positive(),
    name: z.string(),
    company_id: z.number().int().positive(),
    company_name: z.string(),
    product_id: z.union([z.number().int().positive(), z.literal(false)]),
    warehouse_id: z.union([z.number().int().positive(), z.literal(false)]),
    warehouse_name: z.union([z.string(), z.literal(false)]),
    uom: z.union([z.string(), z.literal(false)]),
    created_at: z.string(),
    state: z.enum(['queued', 'running', 'completed', 'insufficient_history', 'no_observed_demand', 'failed']),
    evaluation_status: z.union([z.string(), z.literal(false)]),
    failure_reason: z.union([z.string(), z.literal(false)]),
    source_type: z.enum(['completed_deliveries', 'synthetic_demo']),
    source_label: z.string(),
    sku: z.string(),
    product_name: z.string(),
    horizon_days: z.number().int().positive(),
    history_start: z.string(),
    history_end: z.string(),
    source_cutoff: z.string(),
    source_timezone: z.string(),
    history_days: z.number().int().nonnegative(),
    nonzero_days: z.number().int().nonnegative(),
    source_event_count: z.number().int().nonnegative(),
    source_snapshot_sha256: z.union([z.string(), z.literal(false)]),
    model_version: z.union([z.string(), z.literal(false)]),
    selected_method: z.union([z.string(), z.literal(false)]),
    baseline_method: z.union([z.string(), z.literal(false)]),
    demand_pattern: z.union([z.string(), z.literal(false)]),
    evaluation_days: z.number().int().nonnegative(),
    baseline_mae: z.union([z.number(), z.literal(false)]),
    ml_mae: z.union([z.number(), z.literal(false)]),
    ml_evaluated: z.boolean(),
    review_status: z.enum(['unreviewed', 'reviewed']),
    reviewed_by: z.union([z.string(), z.literal(false)]),
    reviewed_at: z.union([z.string(), z.literal(false)]),
    data_provenance: z.union([z.string(), z.literal(false)]),
    assumptions: z.union([z.string(), z.literal(false)]),
    limitations: z.union([z.string(), z.literal(false)]),
    interval_note: z.union([z.string(), z.literal(false)]),
    current_stock: z.union([
      z.object({ on_hand: z.number(), odoo_projected: z.number(), uom: z.string() }),
      z.literal(false),
    ]),
    observations: z.array(z.object({
      day: z.string(), delivered_units: z.number(), returned_units: z.number(),
      units: z.number(), source_event_count: z.number().int().nonnegative(),
    })).max(730),
    predictions: z.array(z.object({
      day: z.string(), units: z.number(), lower_heuristic: z.number(), upper_heuristic: z.number(),
    })).max(60),
  }),
  history_coverage: z.object({
    configured: z.boolean(),
    complete_from: z.union([z.string(), z.literal(false)]),
    run_starts_within_coverage: z.boolean(),
  }),
  restock_guidance: z.object({
    status: z.enum(['eligible', 'not_eligible', 'not_applicable', 'restricted', 'unavailable']),
    usable: z.boolean(),
    reason: z.string(),
  }),
  read_only: z.literal(true),
})

export const searchSchema = z.object({
  schema_version: z.literal(1),
  query: z.string(),
  limited: z.boolean(),
  results: z.array(z.object({
    id: z.number().int().positive(),
    template_id: z.number().int().positive(),
    name: z.string(),
    sku: z.string(),
    reference: z.union([z.string(), z.literal(false)]),
    category: z.string(),
    supplier_names: z.array(z.string()),
  })),
})

export const productQuickViewSchema = z.object({
  schema_version: z.literal(1),
  company: companySchema,
  read_only: z.literal(true),
  product: z.object({
    id: z.number().int().positive(),
    template_id: z.number().int().positive(),
    name: z.string(),
    sku: z.string(),
    reference: z.union([z.string(), z.literal(false)]),
    category: z.string(),
    tracked: z.boolean(),
  }),
  positions: z.array(riskItemSchema).max(100),
  coverage: z.object({
    complete: z.boolean(),
    candidate_locations: z.number().int().nonnegative(),
    scanned_locations: z.number().int().nonnegative(),
  }),
})

const inventoryWarehouseSchema = z.object({
  id: z.number().int().positive(),
  name: z.string(),
  on_hand: z.number(),
  available: z.number(),
  reserved: z.number(),
  incoming: z.number(),
  outgoing: z.number(),
})

const inventorySupplierSchema = z.union([
  z.object({
    id: z.number().int().positive(),
    name: z.string(),
    lead_time_days: z.number().int().nonnegative(),
    lead_time_label: z.string(),
    minimum_order_qty: z.number().nonnegative(),
    minimum_order_uom: z.string(),
    company_specific: z.boolean(),
  }),
  z.literal(false),
])

const inventoryItemSchema = z.object({
  product_id: z.number().int().positive(),
  template_id: z.number().int().positive(),
  name: z.string(),
  sku: z.string(),
  reference: z.union([z.string(), z.literal(false)]),
  category_id: z.number().int().positive(),
  category: z.string(),
  tracked: z.boolean(),
  active: z.boolean(),
  uom: z.string(),
  status: z.enum(['in_stock', 'low_stock', 'out_of_stock']),
  on_hand: z.number(),
  available: z.number(),
  reserved: z.number(),
  incoming: z.number(),
  outgoing: z.number(),
  projected: z.number(),
  warehouse_count: z.number().int().nonnegative(),
  warehouses: z.array(inventoryWarehouseSchema).max(51),
  supplier: inventorySupplierSchema,
  supplier_access_note: z.union([z.string(), z.literal(false)]),
  supplier_lookup_limited: z.boolean(),
  lead_time_days: z.number().int().nonnegative(),
  lead_time_label: z.string(),
  lead_time_source: z.enum(['supplier', 'planning_assumption']),
})

export const inventoryOptionsSchema = z.object({
  schema_version: z.literal(1),
  company: companySchema,
  warehouses: z.array(z.object({ id: z.number().int().positive(), name: z.string() })).max(51),
  warehouse_options_limited: z.boolean(),
  total_warehouses: z.number().int().nonnegative(),
  categories: z.array(z.object({ id: z.number().int().positive(), name: z.string() })).max(500),
  category_options_limited: z.boolean(),
  suppliers: z.array(z.object({ id: z.number().int().positive(), name: z.string() })).max(500),
  supplier_options_limited: z.boolean(),
  supplier_access: z.boolean(),
  supplier_access_note: z.union([z.string(), z.literal(false)]),
})

export const inventorySchema = z.object({
  schema_version: z.literal(1),
  company: companySchema,
  as_of: z.string(),
  summary: z.object({
    total_tracked: z.number().int().nonnegative(),
    in_stock: z.number().int().nonnegative(),
    low_stock: z.number().int().nonnegative(),
    out_of_stock: z.number().int().nonnegative(),
    complete: z.boolean(),
    sampled_products: z.number().int().nonnegative(),
    total_catalog: z.number().int().nonnegative(),
  }),
  filters: z.object({
    query: z.string(),
    supplier_query: z.string(),
    status: z.enum(['all', 'in_stock', 'low_stock', 'out_of_stock']),
    warehouse_id: z.union([z.number().int().positive(), z.literal(false)]),
    category_id: z.union([z.number().int().positive(), z.literal(false)]),
    supplier_id: z.union([z.number().int().positive(), z.literal(false)]),
    tracked: z.enum(['all', 'tracked', 'not_tracked']),
    active: z.enum(['active', 'archived', 'all']),
    sort: z.enum(['name', 'sku']),
    direction: z.enum(['asc', 'desc']),
  }),
  items: z.array(inventoryItemSchema).max(100),
  pagination: z.object({
    page: z.number().int().positive(),
    page_size: z.number().int().positive().max(100),
    total_count: z.number().int().nonnegative(),
    total_pages: z.number().int().nonnegative(),
    has_previous: z.boolean(),
    has_next: z.boolean(),
    summary_exact: z.boolean(),
    status_scan_used: z.boolean(),
  }),
  coverage: z.object({
    tracked_summary_complete: z.boolean(),
    warehouse_scope_limited: z.boolean(),
    supplier_lines_limited: z.boolean(),
    supplier_terms_available: z.boolean(),
    status_filter_complete: z.boolean(),
  }),
  empty_catalog: z.boolean(),
})

const supplierCount = z.union([z.number().int().nonnegative(), z.literal(false)])
const reorderPositionSchema = z.object({
  warehouse_id: z.number().int().positive(),
  warehouse: z.string(),
  quantity: z.number().nonnegative(),
  uom: z.string(),
})
const supplierPartItemSchema = inventoryItemSchema.extend({
  supplier_terms_count: z.number().int().nonnegative(),
  lead_time_min_days: z.union([z.number().int().nonnegative(), z.literal(false)]),
  lead_time_max_days: z.union([z.number().int().nonnegative(), z.literal(false)]),
  reorder_locations: z.array(reorderPositionSchema).max(5000),
  reorder_parts: z.boolean(),
})

const supplierRowSchema = z.object({
  id: z.number().int().positive(),
  name: z.string(),
  vendor_code: z.union([z.string(), z.literal(false)]),
  company_name: z.union([z.string(), z.literal(false)]),
  email: z.union([z.string(), z.literal(false)]),
  phone: z.union([z.string(), z.literal(false)]),
  city: z.union([z.string(), z.literal(false)]),
  country: z.union([z.string(), z.literal(false)]),
  partner_company: z.union([z.string(), z.literal(false)]),
  active: z.boolean(),
  active_parts: supplierCount,
  tracked_parts: supplierCount,
  low_or_out_parts: supplierCount,
  reorder_parts: supplierCount,
  reorder_locations: supplierCount,
  active_terms: supplierCount,
  has_active_terms: z.boolean(),
  active_terms_status: z.enum(['has_terms', 'no_terms', 'unknown']),
  has_configured_terms: z.boolean(),
  configured_terms_status: z.enum(['has_terms', 'no_terms', 'unknown']),
  lead_time_min_days: z.union([z.number().int().nonnegative(), z.literal(false)]),
  lead_time_max_days: z.union([z.number().int().nonnegative(), z.literal(false)]),
  attention: z.boolean(),
})

export const suppliersSchema = z.object({
  schema_version: z.literal(1),
  company: companySchema,
  as_of: z.string(),
  summary: z.object({
    active_suppliers: supplierCount,
    parts_with_supplier: supplierCount,
    parts_missing_supplier: supplierCount,
    suppliers_with_reorder_needs: supplierCount,
  }),
  filters: z.object({
    query: z.string(),
    attention: z.enum(['all', 'reorder']),
    terms: z.enum(['all', 'active', 'none']),
    sort: z.enum(['name', 'reorder', 'parts', 'lead_time']),
    direction: z.enum(['asc', 'desc']),
  }),
  suppliers: z.array(supplierRowSchema).max(5000),
  pagination: z.object({
    page: z.number().int().positive(),
    page_size: z.number().int().positive().max(50),
    total_count: z.number().int().nonnegative(),
    total_pages: z.number().int().nonnegative(),
    has_previous: z.boolean(),
    has_next: z.boolean(),
  }),
  coverage: z.object({
    supplier_terms_complete: z.boolean(),
    product_catalog_complete: z.boolean(),
    stock_complete: z.boolean(),
    reorder_complete: z.boolean(),
    supplier_limit: z.number().int().positive(),
    term_scan_limit: z.number().int().positive(),
    product_scan_limit: z.number().int().positive(),
    reorder_scan_limit: z.number().int().positive(),
    note: z.union([z.string(), z.literal(false)]),
  }),
  read_only: z.literal(true),
})

export const supplierDetailSchema = z.object({
  schema_version: z.literal(1),
  company: companySchema,
  supplier: z.object({
    id: z.number().int().positive(),
    name: z.string(),
    vendor_code: z.union([z.string(), z.literal(false)]),
    company_name: z.union([z.string(), z.literal(false)]),
    email: z.union([z.string(), z.literal(false)]),
    phone: z.union([z.string(), z.literal(false)]),
    city: z.union([z.string(), z.literal(false)]),
    country: z.union([z.string(), z.literal(false)]),
    partner_company: z.union([z.string(), z.literal(false)]),
  }),
  summary: supplierRowSchema,
  purchase_history: z.object({
    available: z.boolean(),
    note: z.string(),
    items: z.array(z.object({
      id: z.number().int().positive(),
      kind: z.enum(['purchase_order', 'receipt']),
      label: z.string(),
      reference: z.union([z.string(), z.literal(false)]),
      date: z.union([z.string(), z.literal(false)]),
    })).max(10),
  }),
  coverage: z.object({
    supplier_terms_complete: z.boolean(),
    stock_complete: z.boolean(),
    reorder_complete: z.boolean(),
    reorder_scanned: z.number().int().nonnegative(),
    reorder_candidates: z.number().int().nonnegative(),
  }),
  as_of: z.string(),
  read_only: z.literal(true),
})

export const supplierPartsSchema = inventorySchema.extend({
  items: z.array(supplierPartItemSchema).max(100),
  coverage: inventorySchema.shape.coverage.extend({
    supplier_terms_complete: z.boolean(),
    reorder_complete: z.boolean(),
  }),
})

export const supplierGapsSchema = supplierPartsSchema

export const supplierTermsSchema = z.object({
  schema_version: z.literal(1),
  company: companySchema,
  product: z.object({
    id: z.number().int().positive(),
    name: z.string(),
    sku: z.string(),
  }),
  supplier: z.object({ id: z.number().int().positive(), name: z.string() }),
  terms: z.array(z.object({
    id: z.number().int().positive(),
    sequence: z.number().int(),
    vendor_product_name: z.union([z.string(), z.literal(false)]),
    vendor_product_code: z.union([z.string(), z.literal(false)]),
    price: z.union([z.number().nonnegative(), z.literal(false)]),
    price_available: z.boolean(),
    currency: z.object({ code: z.string(), symbol: z.string(), decimal_places: z.number().int().nonnegative() }),
    price_break_min_qty: z.number().nonnegative(),
    price_break_uom: z.string(),
    minimum_order_qty: z.number().nonnegative(),
    minimum_order_uom: z.string(),
    lead_time_days: z.number().int().nonnegative(),
    company_id: z.union([z.number().int().positive(), z.literal(false)]),
    company_name: z.union([z.string(), z.literal(false)]),
    valid_from: z.union([z.string(), z.literal(false)]),
    valid_until: z.union([z.string(), z.literal(false)]),
    active_today: z.boolean(),
    variant_specific: z.boolean(),
  })).max(10000),
  terms_truncated: z.boolean(),
  read_only: z.literal(true),
})

const inventoryDetailWarehouseSchema = inventoryWarehouseSchema.extend({
  selected: z.boolean(),
  projected: z.number(),
})

const inventoryMovementSchema = z.object({
  id: z.number().int().positive(),
  kind: z.enum([
    'adjustment', 'received', 'shipped', 'internal_transfer', 'incoming_purchase',
    'reserved_delivery', 'scheduled_delivery', 'internal_transfer_planned',
  ]),
  label: z.string(),
  date: z.union([z.string(), z.literal(false)]),
  quantity: z.number(),
  uom: z.string(),
  warehouse: z.union([z.string(), z.literal(false)]),
  reference: z.union([z.string(), z.literal(false)]),
})

export const inventoryDetailSchema = z.object({
  schema_version: z.literal(1),
  company: companySchema,
  product: z.object({
    id: z.number().int().positive(),
    template_id: z.number().int().positive(),
    name: z.string(),
    sku: z.string(),
    reference: z.union([z.string(), z.literal(false)]),
    category_id: z.number().int().positive(),
    category: z.string(),
    tracked: z.boolean(),
    active: z.boolean(),
    uom: z.string(),
    safety_stock: z.number(),
  }),
  company_stock: z.object({
    on_hand: z.number(),
    available: z.number(),
    reserved: z.number(),
    incoming: z.number(),
    outgoing: z.number(),
    projected: z.number(),
  }),
  warehouses: z.array(inventoryDetailWarehouseSchema).max(51),
  supplier: inventorySupplierSchema,
  supplier_access: z.boolean(),
  supplier_note: z.union([z.string(), z.literal(false)]),
  lead_time_days: z.number().int().nonnegative(),
  lead_time_label: z.string(),
  lead_time_source: z.enum(['supplier', 'planning_assumption']),
  forecast: z.object({
    status: z.enum(['not_tracked', 'unavailable', 'not_used', 'used']),
    message: z.string(),
    horizon_days: z.union([z.number().int().positive(), z.literal(false)]),
    history_start: z.union([z.string(), z.literal(false)]),
    history_end: z.union([z.string(), z.literal(false)]),
    used_for_restock: z.boolean(),
    demand_before_delivery: z.union([z.number(), z.literal(false)]),
  }),
  recommendations: z.array(riskItemSchema).max(100),
  recommendation_coverage: z.object({
    complete: z.boolean(),
    candidate_locations: z.number().int().nonnegative(),
    scanned_locations: z.number().int().nonnegative(),
    forecast_access_available: z.boolean(),
    forecast_access_reason: z.union([z.string(), z.literal(false)]),
  }),
  movements_available: z.boolean(),
  movements: z.array(inventoryMovementSchema).max(20),
  movement_note: z.string(),
  coverage: z.object({
    warehouse_scope_limited: z.boolean(),
    total_warehouses: z.number().int().nonnegative(),
    supplier_terms_available: z.boolean(),
  }),
  read_only: z.literal(true),
})

const warehouseCountSchema = z.union([z.number().int().nonnegative(), z.literal(false)])

export const warehouseRowSchema = z.object({
  id: z.number().int().positive(),
  name: z.string(),
  code: z.string(),
  company_name: z.string(),
  catalog_parts: warehouseCountSchema,
  tracked_catalog_parts: warehouseCountSchema,
  stocked_parts: warehouseCountSchema,
  tracked_parts_present: warehouseCountSchema,
  low_stock_parts: warehouseCountSchema,
  out_of_stock_parts: warehouseCountSchema,
  parts_with_reserved_stock: warehouseCountSchema,
  parts_with_incoming_stock: warehouseCountSchema,
  parts_with_outgoing_stock: warehouseCountSchema,
  summary_complete: z.boolean(),
  summary_note: z.union([z.string(), z.literal(false)]),
  status: z.enum(['needs_attention', 'healthy', 'no_tracked_stock', 'unknown']),
  recent_activity_at: z.union([z.string(), z.literal(false)]),
  activity_available: z.boolean(),
})

const warehouseMetricsSchema = z.object({
  active_warehouses: z.number().int().nonnegative(),
  warehouses_needing_attention: warehouseCountSchema,
  warehouses_with_low_stock: warehouseCountSchema,
  warehouses_with_stockouts: warehouseCountSchema,
  warehouses_with_incoming: warehouseCountSchema,
  complete: z.boolean(),
})

export const warehousesSchema = z.object({
  schema_version: z.literal(1),
  company: companySchema,
  as_of: z.string(),
  summary: warehouseMetricsSchema,
  filters: z.object({
    query: z.string(),
    status: z.enum(['all', 'attention', 'low_stock', 'out_of_stock', 'healthy', 'no_tracked_stock']),
    sort: z.enum(['name', 'attention', 'recent']),
    direction: z.enum(['asc', 'desc']),
  }),
  warehouses: z.array(warehouseRowSchema).max(50),
  pagination: z.object({
    page: z.number().int().positive(),
    page_size: z.number().int().positive().max(50),
    total_count: z.number().int().nonnegative(),
    total_pages: z.number().int().nonnegative(),
    has_previous: z.boolean(),
    has_next: z.boolean(),
  }),
  coverage: z.object({
    summary_complete: z.boolean(),
    catalog_product_count: z.number().int().nonnegative(),
    catalog_scan_limit: z.number().int().positive(),
    warehouse_count: z.number().int().nonnegative(),
    warehouse_limit: z.number().int().positive(),
    activity_available: z.boolean(),
  }),
})

const warehouseAttentionPartSchema = z.object({
  product_id: z.number().int().positive(),
  name: z.string(),
  sku: z.string(),
  uom: z.string(),
  status: z.enum(['low_stock', 'out_of_stock']),
  on_hand: z.number(),
  available: z.number(),
})

const warehouseActivitySchema = z.object({
  id: z.number().int().positive(),
  kind: z.enum([
    'adjustment', 'received', 'shipped', 'transfer_out', 'transfer_in',
    'incoming_purchase', 'reserved_delivery', 'scheduled_delivery', 'stock_movement',
  ]),
  label: z.string(),
  date: z.union([z.string(), z.literal(false)]),
  completed: z.boolean(),
  product_id: z.number().int().positive(),
  product_name: z.string(),
  sku: z.string(),
  quantity: z.number(),
  uom: z.string(),
  reference: z.union([z.string(), z.literal(false)]),
  counterpart_warehouse: z.union([z.string(), z.literal(false)]),
})

export const warehouseDetailSchema = z.object({
  schema_version: z.literal(1),
  company: companySchema,
  warehouse: z.object({
    id: z.number().int().positive(),
    name: z.string(),
    code: z.string(),
    company_name: z.string(),
  }),
  summary: warehouseRowSchema.pick({
    catalog_parts: true,
    tracked_catalog_parts: true,
    stocked_parts: true,
    tracked_parts_present: true,
    low_stock_parts: true,
    out_of_stock_parts: true,
    parts_with_reserved_stock: true,
    parts_with_incoming_stock: true,
    parts_with_outgoing_stock: true,
    summary_complete: true,
    summary_note: true,
  }).extend({
    reorder_suggestions: warehouseCountSchema,
    reorder_suggestions_complete: z.boolean(),
    reorder_suggestions_note: z.union([z.string(), z.literal(false)]),
  }),
  attention_parts: z.array(warehouseAttentionPartSchema).max(5),
  activity_available: z.boolean(),
  activity: z.array(warehouseActivitySchema).max(20),
  activity_note: z.string(),
  as_of: z.string(),
  read_only: z.literal(true),
})

export type SessionData = z.infer<typeof sessionSchema>
export type DashboardData = z.infer<typeof dashboardSchema>
export type RestockData = z.infer<typeof restockSchema>
export type ForecastData = z.infer<typeof forecastSchema>
export type ForecastsData = z.infer<typeof forecastsSchema>
export type ForecastDetailData = z.infer<typeof forecastDetailSchema>
export type ForecastListRun = z.infer<typeof forecastListRunSchema>
export type ProductSearchData = z.infer<typeof searchSchema>
export type ProductQuickViewData = z.infer<typeof productQuickViewSchema>
export type InventoryOptions = z.infer<typeof inventoryOptionsSchema>
export type InventoryData = z.infer<typeof inventorySchema>
export type InventoryDetailData = z.infer<typeof inventoryDetailSchema>
export type WarehouseData = z.infer<typeof warehousesSchema>
export type WarehouseRow = z.infer<typeof warehouseRowSchema>
export type WarehouseDetailData = z.infer<typeof warehouseDetailSchema>
export type SupplierData = z.infer<typeof suppliersSchema>
export type SupplierRow = z.infer<typeof supplierRowSchema>
export type SupplierDetailData = z.infer<typeof supplierDetailSchema>
export type SupplierPartsData = z.infer<typeof supplierPartsSchema>
export type SupplierPartItem = z.infer<typeof supplierPartItemSchema>
export type SupplierTermsData = z.infer<typeof supplierTermsSchema>
export type SupplierGapsData = z.infer<typeof supplierGapsSchema>
export type ForecastRun = Extract<ForecastData, { status: 'available' }>['forecast']
export type DashboardInsight = z.infer<typeof insightSchema>
export type RiskItem = z.infer<typeof riskItemSchema>
