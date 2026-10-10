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
  }),
  inventory_health: z.object({
    total_tracked: z.number().int().nonnegative(),
    sampled_products: z.number().int().nonnegative(),
    complete: z.boolean(),
    categories: z.array(z.object({
      key: z.enum(['healthy', 'low', 'out']),
      label: z.string(),
      count: z.number().int().nonnegative(),
    })),
  }),
  empty: z.boolean(),
})

const riskItemSchema = z.object({
  key: z.string(),
  product_id: z.number().int().positive(),
  template_id: z.number().int().positive(),
  name: z.string(),
  sku: z.string(),
  warehouse_id: z.number().int().positive(),
  warehouse: z.string(),
  status: z.string(),
  status_label: z.string(),
  current_qty: z.number(),
  uom: z.string(),
  recommended_qty: z.union([z.number(), z.literal(false)]),
  supplier_name: z.union([z.string(), z.literal(false)]),
  reason: z.string(),
  basis_note: z.string(),
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

export const forecastSchema = z.discriminatedUnion('status', [
  z.object({
    schema_version: z.literal(1),
    company: companySchema,
    status: z.literal('available'),
    reason_code: z.literal(false),
    message: z.literal(false),
    forecast: forecastDataSchema,
  }),
  z.object({
    schema_version: z.literal(1),
    company: companySchema,
    status: z.enum(['unavailable', 'restricted']),
    reason_code: z.string(),
    message: z.string(),
    forecast: z.literal(false),
  }),
])

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
  })),
})

export type SessionData = z.infer<typeof sessionSchema>
export type DashboardData = z.infer<typeof dashboardSchema>
export type RestockData = z.infer<typeof restockSchema>
export type ForecastData = z.infer<typeof forecastSchema>
export type ProductSearchData = z.infer<typeof searchSchema>
export type ForecastRun = Extract<ForecastData, { status: 'available' }>['forecast']
