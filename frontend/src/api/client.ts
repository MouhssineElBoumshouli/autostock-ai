import {
  dashboardSchema,
  inventoryDetailSchema,
  inventoryOptionsSchema,
  inventorySchema,
  warehouseDetailSchema,
  warehousesSchema,
  supplierDetailSchema,
  supplierGapsSchema,
  supplierPartsSchema,
  supplierTermsSchema,
  suppliersSchema,
  forecastSchema,
  searchSchema,
  sessionSchema,
  restockSchema,
  productQuickViewSchema,
  type DashboardData,
  type InventoryData,
  type InventoryDetailData,
  type InventoryOptions,
  type WarehouseData,
  type WarehouseDetailData,
  type SupplierData,
  type SupplierDetailData,
  type SupplierPartsData,
  type SupplierTermsData,
  type SupplierGapsData,
  type ForecastData,
  type ProductSearchData,
  type ProductQuickViewData,
  type RestockData,
  type SessionData,
} from './contracts'
import type { ZodType } from 'zod'

const database = import.meta.env.VITE_ODOO_DATABASE?.trim()

export class ApiError extends Error {
  constructor(
    message: string,
    readonly code: 'unauthenticated' | 'forbidden' | 'request' | 'network' | 'contract',
    readonly status?: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function get<T>(path: string, schema: ZodType<T>, companyId?: number): Promise<T> {
  const url = new URL(path, window.location.origin)
  if (companyId) url.searchParams.set('company_id', String(companyId))

  let response: Response
  try {
    response = await fetch(url, {
      method: 'GET',
      credentials: 'include',
      headers: { Accept: 'application/json' },
    })
  } catch {
    throw new ApiError('AutoStock could not reach Odoo. Check your connection and retry.', 'network')
  }

  const contentType = response.headers.get('content-type') ?? ''
  if (!contentType.includes('application/json')) {
    const body = await response.text()
    if (body.toLowerCase().includes('/web/login') || body.toLowerCase().includes('log in')) {
      throw new ApiError('Your Odoo session has ended. Sign in to continue.', 'unauthenticated', response.status)
    }
    throw new ApiError('Odoo returned an unexpected response. Refresh the page and try again.', 'request', response.status)
  }

  const payload: unknown = await response.json()
  if (!response.ok) {
    const error = payload as { error?: { code?: string; message?: string } }
    const code = error.error?.code === 'forbidden' ? 'forbidden' : 'request'
    throw new ApiError(error.error?.message || 'Odoo could not complete that request.', code, response.status)
  }

  const parsed = schema.safeParse(payload)
  if (!parsed.success) {
    throw new ApiError('Odoo returned data that does not match the supported API contract.', 'contract', response.status)
  }
  return parsed.data
}

function requireCompany<T extends { company: { id: number } }>(companyId: number, data: T): T {
  if (data.company.id !== companyId) {
    throw new ApiError('Odoo returned data for a different company. Refresh the Dashboard before continuing.', 'contract')
  }
  return data
}

export const api = {
  session: async (companyId?: number) => {
    const data = await get('/autostock/api/v1/session', sessionSchema, companyId)
    if (companyId && data.current_company.id !== companyId) {
      throw new ApiError('Odoo returned a session for a different company. Refresh the Dashboard before continuing.', 'contract')
    }
    return data
  },
  dashboard: async (companyId: number) => requireCompany(companyId, await get('/autostock/api/v1/dashboard', dashboardSchema, companyId)),
  restock: (companyId: number, warehouseId?: number) => {
    const suffix = warehouseId ? `?warehouse_id=${warehouseId}` : ''
    return get(`/autostock/api/v1/dashboard/restock-preview${suffix}`, restockSchema, companyId).then((data) => requireCompany(companyId, data))
  },
  forecast: (companyId: number, horizonDays = 30, productId?: number, warehouseId?: number) => {
    const params = new URLSearchParams({ horizon_days: String(horizonDays) })
    if (productId) params.set('product_id', String(productId))
    if (warehouseId) params.set('warehouse_id', String(warehouseId))
    return get(`/autostock/api/v1/dashboard/forecast-preview?${params}`, forecastSchema, companyId).then((data) => requireCompany(companyId, data))
  },
  search: (companyId: number, query: string) => {
    const suffix = new URLSearchParams({ q: query }).toString()
    return get(`/autostock/api/v1/search/products?${suffix}`, searchSchema, companyId)
  },
  quickView: (companyId: number, productId: number) => get(
    `/autostock/api/v1/products/${productId}/quick-view`,
    productQuickViewSchema,
    companyId,
  ).then((data) => requireCompany(companyId, data)),
  inventoryOptions: (companyId: number, supplierQuery = '') => {
    const params = new URLSearchParams()
    if (supplierQuery.trim().length >= 2) params.set('supplier_q', supplierQuery.trim())
    return get(`/autostock/api/v1/inventory/options?${params}`, inventoryOptionsSchema, companyId)
      .then((data) => requireCompany(companyId, data))
  },
  inventory: (companyId: number, filters: InventoryRequest = {}) => {
    const params = new URLSearchParams()
    const values: Record<string, string | number | undefined> = {
      q: filters.query,
      supplier_q: filters.supplierQuery,
      status: filters.status,
      warehouse_id: filters.warehouseId,
      category_id: filters.categoryId,
      supplier_id: filters.supplierId,
      tracked: filters.tracked,
      active: filters.active,
      sort: filters.sort,
      direction: filters.direction,
      page: filters.page,
      page_size: filters.pageSize,
    }
    for (const [key, value] of Object.entries(values)) {
      if (value !== undefined && value !== '') params.set(key, String(value))
    }
    return get(`/autostock/api/v1/inventory?${params}`, inventorySchema, companyId)
      .then((data) => requireCompany(companyId, data))
  },
  inventoryDetail: (companyId: number, productId: number, warehouseId?: number) => {
    const params = new URLSearchParams()
    if (warehouseId) params.set('warehouse_id', String(warehouseId))
    return get(
      `/autostock/api/v1/products/${productId}/inventory-detail?${params}`,
      inventoryDetailSchema,
      companyId,
    ).then((data) => requireCompany(companyId, data))
  },
  warehouses: (companyId: number, filters: WarehouseRequest = {}) => {
    const params = new URLSearchParams()
    const values: Record<string, string | number | undefined> = {
      q: filters.query,
      status: filters.status,
      sort: filters.sort,
      direction: filters.direction,
      page: filters.page,
      page_size: filters.pageSize,
    }
    for (const [key, value] of Object.entries(values)) {
      if (value !== undefined && value !== '') params.set(key, String(value))
    }
    return get(`/autostock/api/v1/warehouses?${params}`, warehousesSchema, companyId)
      .then((data) => requireCompany(companyId, data))
  },
  warehouseDetail: (companyId: number, warehouseId: number) => get(
    `/autostock/api/v1/warehouses/${warehouseId}`,
    warehouseDetailSchema,
    companyId,
  ).then((data) => {
    requireCompany(companyId, data)
    if (data.warehouse.id !== warehouseId) {
      throw new ApiError('Odoo returned details for a different warehouse. Refresh the page before continuing.', 'contract')
    }
    return data
  }),
  warehouseInventory: (companyId: number, warehouseId: number, filters: InventoryRequest = {}) => {
    const params = new URLSearchParams()
    const values: Record<string, string | number | undefined> = {
      q: filters.query,
      supplier_q: filters.supplierQuery,
      status: filters.status,
      category_id: filters.categoryId,
      supplier_id: filters.supplierId,
      tracked: filters.tracked,
      active: filters.active,
      sort: filters.sort,
      direction: filters.direction,
      page: filters.page,
      page_size: filters.pageSize,
    }
    for (const [key, value] of Object.entries(values)) {
      if (value !== undefined && value !== '') params.set(key, String(value))
    }
    return get(`/autostock/api/v1/warehouses/${warehouseId}/inventory?${params}`, inventorySchema, companyId)
      .then((data) => {
        requireCompany(companyId, data)
        if (data.filters.warehouse_id !== warehouseId) {
          throw new ApiError('Odoo returned inventory for a different warehouse. Refresh the page before continuing.', 'contract')
        }
        return data
      })
  },
  suppliers: (companyId: number, filters: SupplierRequest = {}) => {
    const params = new URLSearchParams()
    const values: Record<string, string | number | undefined> = {
      q: filters.query,
      attention: filters.attention,
      terms: filters.terms,
      sort: filters.sort,
      direction: filters.direction,
      page: filters.page,
      page_size: filters.pageSize,
    }
    for (const [key, value] of Object.entries(values)) {
      if (value !== undefined && value !== '') params.set(key, String(value))
    }
    return get(`/autostock/api/v1/suppliers?${params}`, suppliersSchema, companyId)
      .then((data) => requireCompany(companyId, data))
  },
  supplierDetail: (companyId: number, supplierId: number) => get(
    `/autostock/api/v1/suppliers/${supplierId}`,
    supplierDetailSchema,
    companyId,
  ).then((data) => {
    requireCompany(companyId, data)
    if (data.supplier.id !== supplierId) {
      throw new ApiError('Odoo returned details for a different supplier. Refresh the page before continuing.', 'contract')
    }
    return data
  }),
  supplierParts: (companyId: number, supplierId: number, filters: SupplierPartsRequest = {}) => {
    const params = new URLSearchParams()
    const values: Record<string, string | number | undefined> = {
      q: filters.query,
      status: filters.status,
      sort: filters.sort,
      direction: filters.direction,
      page: filters.page,
      page_size: filters.pageSize,
    }
    for (const [key, value] of Object.entries(values)) {
      if (value !== undefined && value !== '') params.set(key, String(value))
    }
    return get(`/autostock/api/v1/suppliers/${supplierId}/parts?${params}`, supplierPartsSchema, companyId)
      .then((data) => requireCompany(companyId, data))
  },
  supplierTerms: (companyId: number, supplierId: number, productId: number) => get(
    `/autostock/api/v1/suppliers/${supplierId}/parts/${productId}/terms`,
    supplierTermsSchema,
    companyId,
  ).then((data) => {
    requireCompany(companyId, data)
    if (data.supplier.id !== supplierId || data.product.id !== productId) {
      throw new ApiError('Odoo returned terms for a different supplier or part. Refresh the page before continuing.', 'contract')
    }
    return data
  }),
  supplierGaps: (companyId: number, filters: SupplierGapsRequest = {}) => {
    const params = new URLSearchParams()
    const values: Record<string, string | number | undefined> = {
      q: filters.query,
      status: filters.status,
      sort: filters.sort,
      direction: filters.direction,
      page: filters.page,
      page_size: filters.pageSize,
    }
    for (const [key, value] of Object.entries(values)) {
      if (value !== undefined && value !== '') params.set(key, String(value))
    }
    return get(`/autostock/api/v1/supplier-gaps?${params}`, supplierGapsSchema, companyId)
      .then((data) => requireCompany(companyId, data))
  },
}

export type InventoryRequest = {
  query?: string
  supplierQuery?: string
  status?: 'all' | 'in_stock' | 'low_stock' | 'out_of_stock'
  warehouseId?: number
  categoryId?: number
  supplierId?: number
  tracked?: 'all' | 'tracked' | 'not_tracked'
  active?: 'active' | 'archived' | 'all'
  sort?: 'name' | 'sku'
  direction?: 'asc' | 'desc'
  page?: number
  pageSize?: number
}

export type WarehouseRequest = {
  query?: string
  status?: 'all' | 'attention' | 'low_stock' | 'out_of_stock' | 'healthy' | 'no_tracked_stock'
  sort?: 'name' | 'attention' | 'recent'
  direction?: 'asc' | 'desc'
  page?: number
  pageSize?: number
}

export type SupplierRequest = {
  query?: string
  attention?: 'all' | 'reorder'
  terms?: 'all' | 'active' | 'none'
  sort?: 'name' | 'reorder' | 'parts' | 'lead_time'
  direction?: 'asc' | 'desc'
  page?: number
  pageSize?: number
}

export type SupplierPartsRequest = {
  query?: string
  status?: 'all' | 'in_stock' | 'low_stock' | 'out_of_stock'
  sort?: 'name' | 'sku'
  direction?: 'asc' | 'desc'
  page?: number
  pageSize?: number
}

export type SupplierGapsRequest = SupplierPartsRequest

export async function signIn(login: string, password: string): Promise<void> {
  if (!database) {
    throw new ApiError('The Odoo database is not configured. Set VITE_ODOO_DATABASE in frontend/.env.local.', 'request')
  }

  let response: Response
  try {
    response = await fetch('/web/session/authenticate', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: { db: database, login, password } }),
    })
  } catch {
    throw new ApiError('AutoStock could not reach Odoo. Check your connection and retry.', 'network')
  }

  const payload = await response.json() as {
    result?: { uid?: number | false }
    error?: { data?: { message?: string }; message?: string }
  }
  if (!response.ok || !payload.result?.uid) {
    const detail = payload.error?.data?.message ?? payload.error?.message
    throw new ApiError(detail && !detail.toLowerCase().includes('password') ? detail : 'That email or password was not accepted.', 'unauthenticated', response.status)
  }
}

export async function signOut(): Promise<void> {
  try {
    await fetch('/web/session/destroy', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: {} }),
    })
  } catch {
    // Clearing the browser-side query state below remains a useful sign-out fallback.
  }
}

export function friendlyError(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong while loading your workspace.'
}

export type {
  DashboardData,
  ForecastData,
  InventoryData,
  InventoryDetailData,
  InventoryOptions,
  WarehouseData,
  WarehouseDetailData,
  SupplierData,
  SupplierDetailData,
  SupplierPartsData,
  SupplierTermsData,
  SupplierGapsData,
  ProductSearchData,
  ProductQuickViewData,
  RestockData,
  SessionData,
}
