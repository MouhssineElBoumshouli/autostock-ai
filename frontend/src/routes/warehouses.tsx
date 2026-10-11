import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import {
  AlertCircle, ArrowDown, ArrowDownToLine, ArrowUp, ArrowUpFromLine, Boxes,
  Building2, Check, ChevronLeft, ChevronRight, CircleHelp, Clock3, PackageSearch,
  Search, Warehouse as WarehouseIcon,
} from 'lucide-react'
import { ApiError, api, type InventoryRequest, type WarehouseRequest } from '@/api/client'
import type { InventoryData, WarehouseData, WarehouseDetailData, WarehouseRow } from '@/api/contracts'
import { DashboardShell, type DashboardSection } from '@/components/gate-one/dashboard-shell'
import { InventoryDetailSheet } from '@/components/inventory/inventory-detail-sheet'
import { ProductSearchDialog, type ProductSearchItem } from '@/components/gate-two/product-search-dialog'
import { WorkspaceSession, type WorkspaceSessionValue } from '@/components/workspace-session'
import { useDebounce } from '@/hooks/use-debounce'
import '@/styles/inventory.css'
import '@/styles/warehouses.css'

const WAREHOUSE_PAGE_SIZE = 12
const STOCK_PAGE_SIZE = 25
type InventoryRow = InventoryData['items'][number]
type ProductStub = Pick<ProductSearchItem, 'id' | 'name' | 'sku' | 'reference' | 'category'>
type WarehouseStatus = WarehouseRequest['status']
type ProductStatus = InventoryRequest['status']

function count(value: number | false) {
  return value === false ? '—' : new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value)
}

function quantity(value: number, uom: string) {
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value)} ${uom}`
}

function dateLabel(value: string | false, locale: string, timezone: string) {
  if (!value) return 'No completed changes in the last 90 days'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Recent stock activity'
  try {
    return new Intl.DateTimeFormat(locale.replaceAll('_', '-'), {
      dateStyle: 'medium', timeStyle: 'short', timeZone: timezone,
    }).format(date)
  } catch {
    return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(date)
  }
}

function warehouseStatusLabel(status: WarehouseRow['status']) {
  if (status === 'needs_attention') return 'Needs attention'
  if (status === 'healthy') return 'Stock available'
  if (status === 'no_tracked_stock') return 'No tracked stock'
  return 'Summary unavailable'
}

function WarehouseStatus({ status }: { status: WarehouseRow['status'] }) {
  return <span className={`warehouse-status is-${status}`}><i aria-hidden="true" />{warehouseStatusLabel(status)}</span>
}

function productStatusLabel(status: InventoryRow['status']) {
  if (status === 'out_of_stock') return 'Out of stock'
  if (status === 'low_stock') return 'Low stock'
  return 'In stock'
}

function ProductStatus({ status }: { status: InventoryRow['status'] }) {
  return <span className={`inventory-status is-${status}`}><i aria-hidden="true" />{productStatusLabel(status)}</span>
}

function warehouseState(summary: WarehouseDetailData['summary']): WarehouseRow['status'] {
  if (!summary.summary_complete) return 'unknown'
  if (summary.low_stock_parts || summary.out_of_stock_parts) return 'needs_attention'
  if (summary.stocked_parts || summary.parts_with_incoming_stock || summary.parts_with_outgoing_stock) return 'healthy'
  return 'no_tracked_stock'
}

function WarehouseLoading({ detail = false }: { detail?: boolean }) {
  return (
    <section className="warehouse-loading panel" role="status" aria-label={detail ? 'Loading warehouse' : 'Loading warehouses'}>
      <span className="sr-only">{detail ? 'Loading warehouse details…' : 'Loading warehouses…'}</span>
      <span /><span /><span />
    </section>
  )
}

function WarehouseError({ error, onRetry, detail = false }: { error: Error; onRetry: () => void; detail?: boolean }) {
  const forbidden = error instanceof ApiError && error.code === 'forbidden'
  return (
    <section className="inventory-state panel" role="alert">
      <span className="inventory-state-icon is-error"><AlertCircle size={21} aria-hidden="true" /></span>
      <h2>{forbidden ? 'Warehouse access is restricted' : `${detail ? 'Warehouse details' : 'Warehouses'} could not be loaded`}</h2>
      <p>{forbidden ? 'Your current role cannot read warehouse stock for this company. Ask your administrator to review your Inventory access.' : error.message}</p>
      {!forbidden && <button className="inventory-secondary-button" type="button" onClick={onRetry}>Try again</button>}
    </section>
  )
}

function OverviewMetrics({ data }: { data: WarehouseData }) {
  const values = data.summary
  const metrics = [
    { label: 'Warehouses', value: values.active_warehouses, note: 'In this company', tone: 'violet', icon: WarehouseIcon },
    { label: 'Need attention', value: values.warehouses_needing_attention, note: 'Warehouses with low or out-of-stock parts', tone: 'amber', icon: AlertCircle },
    { label: 'With stockouts', value: values.warehouses_with_stockouts, note: 'Warehouses with tracked parts at zero', tone: 'red', icon: PackageSearch },
    { label: 'With incoming stock', value: values.warehouses_with_incoming, note: 'Warehouses expecting incoming stock', tone: 'green', icon: ArrowDownToLine },
  ]
  return (
    <>
      <div className="inventory-summary-grid warehouse-overview-metrics" aria-label="Warehouse overview">
        {metrics.map(({ label, value, note, tone, icon: Icon }) => (
          <article className={`inventory-summary-card tone-${tone}`} key={label}>
            <span className="inventory-summary-icon"><Icon size={17} aria-hidden="true" /></span>
            <div className="inventory-summary-copy"><span>{label}</span><strong>{count(value)}</strong><small>{note}</small></div>
          </article>
        ))}
      </div>
      {!values.complete && (
        <p className="inventory-summary-caveat" role="note"><CircleHelp size={14} aria-hidden="true" />Some stock attention counts are unavailable because the company catalog exceeds the safe summary scan limit.</p>
      )}
    </>
  )
}

function WarehouseCard({ row, locale, timezone }: { row: WarehouseRow; locale: string; timezone: string }) {
  return (
    <Link className="warehouse-card" to="/warehouses/$warehouseId" params={{ warehouseId: String(row.id) }} aria-label={`Open ${row.name} warehouse details`}>
      <div className="warehouse-card-heading">
        <span className="warehouse-card-icon"><WarehouseIcon size={19} aria-hidden="true" /></span>
        <div className="warehouse-card-name"><h2>{row.name}</h2><span>{row.code} <i aria-hidden="true">·</i> {row.company_name}</span></div>
        <WarehouseStatus status={row.status} />
      </div>
      <div className="warehouse-card-metrics">
        <div><span>Parts with stock</span><strong>{count(row.stocked_parts)}</strong></div>
        <div className="is-alert"><span>Low stock</span><strong>{count(row.low_stock_parts)}</strong></div>
        <div className="is-critical"><span>Out of stock</span><strong>{count(row.out_of_stock_parts)}</strong></div>
      </div>
      <div className="warehouse-card-movement">
        <span><Clock3 size={14} aria-hidden="true" />{row.activity_available ? dateLabel(row.recent_activity_at, locale, timezone) : 'Stock activity is restricted for your role'}</span>
        <span className="warehouse-card-open">View warehouse <ChevronRight size={15} aria-hidden="true" /></span>
      </div>
      {!row.summary_complete && row.summary_note && <p className="warehouse-card-note"><CircleHelp size={13} aria-hidden="true" />{row.summary_note}</p>}
    </Link>
  )
}

function WarehouseOverview({ companyId, session, onSwitchCompany, onSignOut }: WorkspaceSessionValue) {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<WarehouseStatus>('all')
  const [sort, setSort] = useState<WarehouseRequest['sort']>('attention')
  const [direction, setDirection] = useState<WarehouseRequest['direction']>('desc')
  const [page, setPage] = useState(1)
  const [selectedProduct, setSelectedProduct] = useState<ProductStub | null>(null)
  const debouncedQuery = useDebounce(query.trim(), 250)
  const request: WarehouseRequest = { query: debouncedQuery, status, sort, direction, page, pageSize: WAREHOUSE_PAGE_SIZE }
  const warehouses = useQuery({
    queryKey: ['warehouses', companyId, request],
    queryFn: () => api.warehouses(companyId, request),
    placeholderData: keepPreviousData,
  })
  const data = warehouses.data
  const company = session.allowed_companies.find((item) => item.id === companyId) ?? session.current_company
  const filtered = Boolean(debouncedQuery || status !== 'all')

  function resetFilters() {
    setQuery('')
    setStatus('all')
    setSort('attention')
    setDirection('desc')
    setPage(1)
  }

  return (
    <WarehouseWorkspace workspace={{ session, companyId, onSwitchCompany, onSignOut }} activeSection="warehouses" selectedProduct={selectedProduct} onSelectProduct={setSelectedProduct}>
      <main className="page-content inventory-page warehouse-page" id="warehouses-top">
        <div className="page-heading inventory-page-heading warehouse-page-heading">
          <div>
            <div className="inventory-eyebrow"><WarehouseIcon size={14} aria-hidden="true" /> Locations and stock</div>
            <h1>Warehouses</h1>
            <p>See where parts are stored, which locations need attention, and what stock is moving at {company.name}.</p>
          </div>
          <span className="warehouse-readonly-mark"><Check size={14} aria-hidden="true" /> Read-only view</span>
        </div>

        {warehouses.isError && !data ? (
          <WarehouseError error={warehouses.error} onRetry={() => void warehouses.refetch()} />
        ) : warehouses.isPending && !data ? (
          <WarehouseLoading />
        ) : data ? (
          <>
            <OverviewMetrics data={data} />
            <section className="warehouse-catalog panel" aria-labelledby="warehouse-list-title">
              <div className="warehouse-section-heading">
                <div className="inventory-catalog-title">
                  <span className="inventory-catalog-icon"><Building2 size={18} aria-hidden="true" /></span>
                  <div><h2 id="warehouse-list-title">Your locations</h2><p>Part counts are positions, not combined quantities. Each part keeps its own unit.</p></div>
                </div>
                <span className="inventory-live-mark"><i aria-hidden="true" /> Current stock</span>
              </div>
              <div className="warehouse-filter-area">
                <label className="inventory-search-field">
                  <Search size={16} aria-hidden="true" />
                  <span className="sr-only">Search warehouses by name or code</span>
                  <input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1) }} placeholder="Search warehouse name or code…" type="search" autoComplete="off" />
                  {query && <button type="button" aria-label="Clear warehouse search" onClick={() => { setQuery(''); setPage(1) }}>Clear</button>}
                </label>
                <div className="warehouse-filters">
                  <label className="inventory-select-wrap"><span>Attention</span>
                    <select aria-label="Filter warehouses by stock status" value={status} onChange={(event) => { setStatus(event.target.value as WarehouseStatus); setPage(1) }}>
                      <option value="all">All warehouses</option><option value="attention">Needs attention</option><option value="low_stock">Low stock</option><option value="out_of_stock">Stockouts</option><option value="healthy">Stock available</option><option value="no_tracked_stock">No tracked stock</option>
                    </select>
                  </label>
                  <label className="inventory-select-wrap"><span>Sort by</span>
                    <select aria-label="Sort warehouses by" value={sort} onChange={(event) => { setSort(event.target.value as WarehouseRequest['sort']); setPage(1) }}>
                      <option value="attention">Attention</option><option value="name">Name</option><option value="recent">Recent activity</option>
                    </select>
                  </label>
                  <button className="warehouse-direction" type="button" aria-label={`Sort ${direction === 'asc' ? 'descending' : 'ascending'}`} onClick={() => { setDirection((value) => value === 'asc' ? 'desc' : 'asc'); setPage(1) }}>
                    {direction === 'asc' ? <ArrowDown size={14} aria-hidden="true" /> : <ArrowUp size={14} aria-hidden="true" />}
                  </button>
                </div>
              </div>

              {warehouses.isError ? (
                <div className="inventory-inline-error" role="alert"><AlertCircle size={16} aria-hidden="true" /><span>{warehouses.error.message}</span><button type="button" onClick={() => void warehouses.refetch()}>Retry</button></div>
              ) : warehouses.isFetching && !data.warehouses.length ? (
                <div className="warehouse-results-loading" role="status">Updating warehouse results…</div>
              ) : data.warehouses.length ? (
                <div className="warehouse-grid">
                  {data.warehouses.map((row) => <WarehouseCard key={row.id} row={row} locale={session.user.locale} timezone={session.user.timezone} />)}
                </div>
              ) : (
                <section className="warehouse-empty" aria-live="polite">
                  <span className="inventory-state-icon"><WarehouseIcon size={21} aria-hidden="true" /></span>
                  <h2>{filtered ? 'No warehouses match these filters' : 'No warehouses are set up yet'}</h2>
                  <p>{filtered ? 'Try a different name or attention filter.' : 'Once a warehouse is configured for this company, its stock and activity will appear here.'}</p>
                  {filtered && <button className="inventory-secondary-button" type="button" onClick={resetFilters}>Clear filters</button>}
                </section>
              )}

              <div className="inventory-pagination warehouse-pagination">
                <span>Showing <strong>{data.pagination.total_count ? (data.pagination.page - 1) * data.pagination.page_size + 1 : 0}–{Math.min(data.pagination.page * data.pagination.page_size, data.pagination.total_count)}</strong> of <strong>{count(data.pagination.total_count)}</strong></span>
                <div><button type="button" aria-label="Previous page" disabled={!data.pagination.has_previous || warehouses.isFetching} onClick={() => setPage((value) => Math.max(1, value - 1))}><ChevronLeft size={16} aria-hidden="true" />Previous</button><span>Page {data.pagination.page} of {data.pagination.total_pages || 1}</span><button type="button" aria-label="Next page" disabled={!data.pagination.has_next || warehouses.isFetching} onClick={() => setPage((value) => value + 1)}>Next<ChevronRight size={16} aria-hidden="true" /></button></div>
              </div>
              {!data.coverage.summary_complete && <p className="inventory-coverage-note">The warehouse overview is limited by a safe scan cap. Per-part stock search remains available inside each warehouse.</p>}
            </section>
          </>
        ) : null}
      </main>
    </WarehouseWorkspace>
  )
}

function WarehouseSummaryMetrics({ data }: { data: WarehouseDetailData }) {
  const summary = data.summary
  const metrics = [
    { label: 'Parts in catalog', value: summary.catalog_parts, note: 'Active storable parts', tone: 'violet', icon: Boxes },
    { label: 'Parts with stock', value: summary.stocked_parts, note: 'Physical stock above zero', tone: 'green', icon: PackageSearch },
    { label: 'Low stock', value: summary.low_stock_parts, note: 'At or below the set level', tone: 'amber', icon: ArrowDown },
    { label: 'Out of stock', value: summary.out_of_stock_parts, note: 'Tracked parts at zero', tone: 'red', icon: AlertCircle },
  ]
  return (
    <>
      <div className="inventory-summary-grid warehouse-detail-metrics" aria-label={`${data.warehouse.name} stock summary`}>
        {metrics.map(({ label, value, note, tone, icon: Icon }) => <article className={`inventory-summary-card tone-${tone}`} key={label}><span className="inventory-summary-icon"><Icon size={17} aria-hidden="true" /></span><div className="inventory-summary-copy"><span>{label}</span><strong>{count(value)}</strong><small>{note}</small></div></article>)}
      </div>
      <div className="warehouse-position-strip" aria-label="Part positions with current stock activity">
        <span><strong>{count(summary.parts_with_reserved_stock)}</strong> parts with reserved stock</span>
        <span><strong>{count(summary.parts_with_incoming_stock)}</strong> parts with incoming stock</span>
        <span><strong>{count(summary.parts_with_outgoing_stock)}</strong> parts with outgoing stock</span>
        <span><strong>{count(summary.reorder_suggestions)}</strong> reorder suggestions</span>
      </div>
      {!summary.summary_complete && <p className="inventory-summary-caveat" role="note"><CircleHelp size={14} aria-hidden="true" />{summary.summary_note || 'The part catalog is larger than the safe summary scan limit. Search individual parts below for reliable quantities.'}</p>}
      {!summary.reorder_suggestions_complete && summary.reorder_suggestions_note && <p className="inventory-summary-caveat" role="note"><CircleHelp size={14} aria-hidden="true" />{summary.reorder_suggestions_note}</p>}
    </>
  )
}

function AttentionParts({ parts }: { parts: WarehouseDetailData['attention_parts'] }) {
  if (!parts.length) return null
  return (
    <section className="warehouse-attention panel" aria-labelledby="warehouse-attention-title">
      <div className="warehouse-detail-section-heading"><div><h2 id="warehouse-attention-title">Parts to check</h2><p>Tracked parts that are out of stock or low on stock in this warehouse.</p></div><span>{parts.length} shown</span></div>
      <div className="warehouse-attention-list">
        {parts.map((part) => <div className="warehouse-attention-row" key={part.product_id}>
          <span className={`warehouse-attention-icon is-${part.status}`}><PackageSearch size={16} aria-hidden="true" /></span>
          <span className="warehouse-attention-name"><strong>{part.name}</strong><small>SKU {part.sku}</small></span>
          <span className="warehouse-attention-qty"><small>On hand</small><strong>{quantity(part.on_hand, part.uom)}</strong></span>
          <span className="warehouse-attention-qty"><small>Available</small><strong>{quantity(part.available, part.uom)}</strong></span>
          <ProductStatus status={part.status} />
        </div>)}
      </div>
    </section>
  )
}

function ActivityFeed({ data, locale, timezone }: { data: WarehouseDetailData; locale: string; timezone: string }) {
  return (
    <section className="warehouse-activity panel" aria-labelledby="warehouse-activity-title">
      <div className="warehouse-detail-section-heading"><div><h2 id="warehouse-activity-title">Recent stock activity</h2><p>Completed changes and current expected movements, in this warehouse’s locations.</p></div><Clock3 size={17} aria-hidden="true" /></div>
      {!data.activity_available ? (
        <div className="warehouse-activity-state"><CircleHelp size={17} aria-hidden="true" /><p>{data.activity_note}</p></div>
      ) : data.activity.length ? (
        <div className="warehouse-activity-list">
          {data.activity.map((activity) => {
            const isIn = activity.kind === 'received' || activity.kind === 'incoming_purchase' || activity.kind === 'transfer_in'
            const isOut = activity.kind === 'shipped' || activity.kind === 'reserved_delivery' || activity.kind === 'scheduled_delivery' || activity.kind === 'transfer_out'
            const Icon = isIn ? ArrowDownToLine : isOut ? ArrowUpFromLine : PackageSearch
            return <article className="warehouse-activity-row" key={activity.id}>
              <span className={`warehouse-activity-icon ${isIn ? 'is-in' : isOut ? 'is-out' : ''}`}><Icon size={15} aria-hidden="true" /></span>
              <span className="warehouse-activity-copy"><strong>{activity.label}</strong><span>{activity.product_name} <small>SKU {activity.sku}</small></span><small>{activity.reference || 'No reference'}{activity.counterpart_warehouse ? ` · ${activity.counterpart_warehouse}` : ''}</small></span>
              <span className="warehouse-activity-amount"><strong>{quantity(activity.quantity, activity.uom)}</strong><small>{activity.completed ? 'Completed' : 'Planned'}</small></span>
              <time dateTime={activity.date || undefined}>{dateLabel(activity.date, locale, timezone)}</time>
            </article>
          })}
        </div>
      ) : <div className="warehouse-activity-state"><Clock3 size={17} aria-hidden="true" /><p>{data.activity_note}</p></div>}
      {data.activity.length > 0 && <p className="warehouse-activity-note">{data.activity_note}</p>}
    </section>
  )
}

function stockRows(data: InventoryData, openProduct: (item: InventoryRow) => void, loading: boolean) {
  return (
    <>
      <div className="warehouse-stock-table-wrap">
        <table className="warehouse-stock-table">
          <thead><tr>
            <th scope="col">Part</th><th scope="col">SKU</th><th scope="col">On hand<span>physical stock</span></th><th scope="col">Available to use<span>not reserved</span></th><th scope="col">Reserved</th><th scope="col">Incoming</th><th scope="col">Outgoing</th><th scope="col">Status</th>
          </tr></thead>
          <tbody>{data.items.map((item) => <tr key={item.product_id}>
            <td><button type="button" className="warehouse-stock-part" onClick={() => openProduct(item)} aria-label={`Open details for ${item.name}`}><span className="inventory-part-icon"><PackageSearch size={15} aria-hidden="true" /></span><span><strong>{item.name}</strong><small>{item.category}{item.reference ? ` · OEM ${item.reference}` : ''}</small></span></button></td>
            <td className="warehouse-stock-sku">{item.sku}</td>
            <td>{quantity(item.on_hand, item.uom)}</td><td>{quantity(item.available, item.uom)}</td><td>{quantity(item.reserved, item.uom)}</td><td>{quantity(item.incoming, item.uom)}</td><td>{quantity(item.outgoing, item.uom)}</td><td><ProductStatus status={item.status} /></td>
          </tr>)}</tbody>
        </table>
      </div>
      <div className="warehouse-stock-mobile">
        {data.items.map((item) => <button className="warehouse-stock-mobile-card" key={item.product_id} type="button" onClick={() => openProduct(item)} aria-label={`Open details for ${item.name}`}>
          <span className="warehouse-stock-mobile-heading"><span><strong>{item.name}</strong><small>SKU {item.sku}{item.reference ? ` · OEM ${item.reference}` : ''}</small></span><ProductStatus status={item.status} /></span>
          <span className="warehouse-stock-mobile-values"><span>On hand<strong>{quantity(item.on_hand, item.uom)}</strong></span><span>Available to use<strong>{quantity(item.available, item.uom)}</strong></span><span>Reserved<strong>{quantity(item.reserved, item.uom)}</strong></span><span>Incoming<strong>{quantity(item.incoming, item.uom)}</strong></span><span>Outgoing<strong>{quantity(item.outgoing, item.uom)}</strong></span></span>
          <span className="warehouse-stock-mobile-supplier">{item.supplier ? `Supplier · ${item.supplier.name}` : item.supplier_access_note ? 'Supplier details restricted' : 'No supplier on file'}</span>
        </button>)}
      </div>
      {loading && <div className="warehouse-fetching" role="status">Updating parts…</div>}
    </>
  )
}

function WarehouseInventory({ companyId, warehouseId, openProduct }: { companyId: number; warehouseId: number; openProduct: (item: InventoryRow) => void }) {
  const [query, setQuery] = useState('')
  const [supplierQuery, setSupplierQuery] = useState('')
  const [status, setStatus] = useState<ProductStatus>('all')
  const [categoryId, setCategoryId] = useState<number | undefined>()
  const [tracked, setTracked] = useState<InventoryRequest['tracked']>('all')
  const [sort, setSort] = useState<InventoryRequest['sort']>('name')
  const [direction, setDirection] = useState<InventoryRequest['direction']>('asc')
  const [page, setPage] = useState(1)
  const debouncedQuery = useDebounce(query.trim(), 250)
  const debouncedSupplier = useDebounce(supplierQuery.trim(), 250)
  const options = useQuery({
    queryKey: ['inventory-options', companyId, debouncedSupplier],
    queryFn: () => api.inventoryOptions(companyId, debouncedSupplier),
  })
  const request: InventoryRequest = {
    query: debouncedQuery,
    supplierQuery: options.data?.supplier_access ? debouncedSupplier : undefined,
    status,
    categoryId,
    tracked,
    active: 'active',
    sort,
    direction,
    page,
    pageSize: STOCK_PAGE_SIZE,
  }
  const inventory = useQuery({
    queryKey: ['warehouse-inventory', companyId, warehouseId, request],
    queryFn: () => api.warehouseInventory(companyId, warehouseId, request),
    placeholderData: keepPreviousData,
  })
  const data = inventory.data
  const filtered = Boolean(debouncedQuery || debouncedSupplier || status !== 'all' || categoryId || tracked !== 'all')

  function resetFilters() {
    setQuery('')
    setSupplierQuery('')
    setStatus('all')
    setCategoryId(undefined)
    setTracked('all')
    setSort('name')
    setDirection('asc')
    setPage(1)
  }

  return (
    <section className="warehouse-stock panel" aria-labelledby="warehouse-stock-title">
      <div className="warehouse-section-heading">
        <div className="inventory-catalog-title"><span className="inventory-catalog-icon"><Boxes size={18} aria-hidden="true" /></span><div><h2 id="warehouse-stock-title">Parts in this warehouse</h2><p>Each quantity is shown in that part’s own unit. Available to use is stock not reserved for orders.</p></div></div>
        <span className="inventory-live-mark"><i aria-hidden="true" /> Current stock</span>
      </div>
      <div className="warehouse-stock-filters">
        <label className="inventory-search-field"><Search size={16} aria-hidden="true" /><span className="sr-only">Search by part name, SKU, OEM reference</span><input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1) }} type="search" placeholder="Search name, SKU, or OEM reference…" autoComplete="off" />{query && <button type="button" aria-label="Clear part search" onClick={() => { setQuery(''); setPage(1) }}>Clear</button>}</label>
        <div className="warehouse-stock-filter-row">
          <label className="inventory-select-wrap"><span>Stock status</span><select aria-label="Filter warehouse parts by stock status" value={status} onChange={(event) => { setStatus(event.target.value as ProductStatus); setPage(1) }}><option value="all">All statuses</option><option value="in_stock">In stock</option><option value="low_stock">Low stock</option><option value="out_of_stock">Out of stock</option></select></label>
          <label className="inventory-select-wrap"><span>Category</span><select aria-label="Filter warehouse parts by category" value={categoryId ?? ''} onChange={(event) => { setCategoryId(event.target.value ? Number(event.target.value) : undefined); setPage(1) }} disabled={options.isPending}><option value="">All categories</option>{options.data?.categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
          <label className="inventory-select-wrap"><span>Monitoring</span><select aria-label="Filter warehouse parts by monitoring" value={tracked} onChange={(event) => { setTracked(event.target.value as InventoryRequest['tracked']); setPage(1) }}><option value="all">All parts</option><option value="tracked">Monitored</option><option value="not_tracked">Not monitored</option></select></label>
          {options.data?.supplier_access && <label className="inventory-select-wrap warehouse-supplier-filter"><span>Supplier</span><input aria-label="Filter warehouse parts by supplier" value={supplierQuery} onChange={(event) => { setSupplierQuery(event.target.value); setPage(1) }} placeholder="Search supplier…" list="warehouse-supplier-options" /><datalist id="warehouse-supplier-options">{options.data.suppliers.map((supplier) => <option key={supplier.id} value={supplier.name} />)}</datalist></label>}
          <label className="inventory-select-wrap"><span>Sort by</span><select aria-label="Sort warehouse parts by" value={sort} onChange={(event) => { setSort(event.target.value as InventoryRequest['sort']); setPage(1) }}><option value="name">Part name</option><option value="sku">SKU</option></select></label>
          <button className="warehouse-direction" type="button" aria-label={`Sort ${direction === 'asc' ? 'descending' : 'ascending'}`} onClick={() => { setDirection((value) => value === 'asc' ? 'desc' : 'asc'); setPage(1) }}>{direction === 'asc' ? <ArrowDown size={14} aria-hidden="true" /> : <ArrowUp size={14} aria-hidden="true" />}</button>
        </div>
      </div>
      {inventory.isError && !data ? (
        <WarehouseError error={inventory.error} onRetry={() => void inventory.refetch()} detail />
      ) : inventory.isPending && !data ? (
        <div className="warehouse-results-loading" role="status">Loading parts in this warehouse…</div>
      ) : data && data.items.length ? (
        <>
          {stockRows(data, openProduct, inventory.isFetching)}
          <div className="inventory-pagination warehouse-pagination"><span>Showing <strong>{(data.pagination.page - 1) * data.pagination.page_size + 1}–{Math.min(data.pagination.page * data.pagination.page_size, data.pagination.total_count)}</strong> of <strong>{count(data.pagination.total_count)}</strong> parts</span><div><button type="button" aria-label="Previous parts page" disabled={!data.pagination.has_previous || inventory.isFetching} onClick={() => setPage((value) => Math.max(1, value - 1))}><ChevronLeft size={16} aria-hidden="true" />Previous</button><span>Page {data.pagination.page} of {data.pagination.total_pages || 1}</span><button type="button" aria-label="Next parts page" disabled={!data.pagination.has_next || inventory.isFetching} onClick={() => setPage((value) => value + 1)}>Next<ChevronRight size={16} aria-hidden="true" /></button></div></div>
          {data.pagination.status_scan_used && <p className="inventory-coverage-note">Stock status was checked on the server across the matching warehouse catalog before paging.</p>}
        </>
      ) : data ? (
        <div className="warehouse-empty warehouse-stock-empty"><span className="inventory-state-icon"><PackageSearch size={21} aria-hidden="true" /></span><h2>{filtered ? 'No parts match these filters' : 'No parts are stored here yet'}</h2><p>{filtered ? 'Try a different search or clear one or more filters.' : 'Parts placed in this warehouse will appear with their current stock here.'}</p>{filtered && <button className="inventory-secondary-button" type="button" onClick={resetFilters}>Clear filters</button>}</div>
      ) : null}
      {options.data?.supplier_access_note && <p className="inventory-coverage-note">Supplier details are restricted for your role. Part search, stock, and category filters remain available.</p>}
    </section>
  )
}

function WarehouseDetail({ companyId, warehouseId, session, onSwitchCompany, onSignOut }: WorkspaceSessionValue & { warehouseId: number }) {
  const [selectedProduct, setSelectedProduct] = useState<ProductStub | null>(null)
  const detail = useQuery({
    queryKey: ['warehouse-detail', companyId, warehouseId],
    queryFn: () => api.warehouseDetail(companyId, warehouseId),
  })
  const data = detail.data
  const openProduct = useCallback((item: InventoryRow) => setSelectedProduct({
    id: item.product_id, name: item.name, sku: item.sku, reference: item.reference, category: item.category,
  }), [])

  return (
    <WarehouseWorkspace workspace={{ session, companyId, onSwitchCompany, onSignOut }} activeSection="warehouses" warehouseId={warehouseId} selectedProduct={selectedProduct} onSelectProduct={setSelectedProduct}>
      <main className="page-content inventory-page warehouse-page warehouse-detail-page" id="warehouse-detail-top">
        <Link className="warehouse-back-link" to="/warehouses"><ChevronLeft size={15} aria-hidden="true" />All warehouses</Link>
        {detail.isError && !data ? <WarehouseError error={detail.error} onRetry={() => void detail.refetch()} detail /> : detail.isPending && !data ? <WarehouseLoading detail /> : data ? <>
          <div className="page-heading inventory-page-heading warehouse-page-heading warehouse-detail-heading">
            <div><div className="inventory-eyebrow"><WarehouseIcon size={14} aria-hidden="true" /> Warehouse details <span>·</span> {data.warehouse.code}</div><h1>{data.warehouse.name}</h1><p>Stock levels and recent movements across this warehouse’s locations.</p></div>
            <WarehouseStatus status={warehouseState(data.summary)} />
          </div>
          <WarehouseSummaryMetrics data={data} />
          <AttentionParts parts={data.attention_parts} />
          <WarehouseInventory companyId={companyId} warehouseId={warehouseId} openProduct={openProduct} />
          <ActivityFeed data={data} locale={session.user.locale} timezone={session.user.timezone} />
          <p className="inventory-page-footnote">Stock is read-only here. On hand means physical stock; available to use means stock not reserved for active orders. Part quantities are never combined across different units.</p>
        </> : null}
      </main>
    </WarehouseWorkspace>
  )
}

function WarehouseWorkspace({
  workspace, activeSection, warehouseId, selectedProduct, onSelectProduct, children,
}: {
  workspace: WorkspaceSessionValue
  activeSection: DashboardSection
  warehouseId?: number
  selectedProduct?: ProductStub | null
  onSelectProduct?: (product: ProductStub | null) => void
  children: ReactNode
}) {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const navigate = useNavigate()
  const { session, companyId, onSwitchCompany, onSignOut } = workspace
  const productDetailStub: ProductStub | null = selectedProduct ?? null

  useEffect(() => {
    function onShortcut(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setSearchOpen((open) => !open)
      }
    }
    window.addEventListener('keydown', onShortcut)
    return () => window.removeEventListener('keydown', onShortcut)
  }, [])

  function navigateTo(section: DashboardSection) {
    if (section === 'dashboard') void navigate({ to: '/' })
    if (section === 'inventory') void navigate({ to: '/inventory' })
    if (section === 'warehouses') void navigate({ to: '/warehouses' })
    if (section === 'forecast') void navigate({ to: '/' })
  }

  return (
    <>
      <DashboardShell collapsed={collapsed} onToggleCollapsed={() => setCollapsed((value) => !value)} activeSection={activeSection} onNavigate={navigateTo} onUnavailable={() => undefined} onOpenSearch={() => setSearchOpen(true)} mobileNavOpen={mobileNavOpen} onMobileNavChange={setMobileNavOpen} session={session} companyId={companyId} onSwitchCompany={onSwitchCompany} onSignOut={onSignOut}>
        {children}
      </DashboardShell>
      <ProductSearchDialog companyId={companyId} open={searchOpen} onOpenChange={setSearchOpen} onSelectProduct={(product) => {
        const next = { id: product.id, name: product.name, sku: product.sku, reference: product.reference, category: product.category }
        onSelectProduct?.(next)
        setSearchOpen(false)
      }} />
      {productDetailStub && <InventoryDetailSheet product={{ product_id: productDetailStub.id, name: productDetailStub.name, sku: productDetailStub.sku, reference: productDetailStub.reference, category: productDetailStub.category }} companyId={companyId} warehouseId={warehouseId} locale={session.user.locale} timezone={session.user.timezone} onClose={() => onSelectProduct?.(null)} />}
    </>
  )
}

export function WarehousesPage() {
  return <WorkspaceSession>{(value) => <WarehouseOverview {...value} />}</WorkspaceSession>
}

export function WarehouseDetailPage({ warehouseId }: { warehouseId: number }) {
  return <WorkspaceSession>{(value) => <WarehouseDetail {...value} warehouseId={warehouseId} />}</WorkspaceSession>
}
