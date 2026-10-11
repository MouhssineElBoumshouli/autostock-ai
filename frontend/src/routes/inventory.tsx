import { useCallback, useEffect, useState } from 'react'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import {
  AlertCircle, ArrowDown, ArrowUp, Boxes, ChevronLeft, ChevronRight,
  CircleHelp, Filter, PackageSearch, Search, Warehouse,
} from 'lucide-react'
import { ApiError, api, type InventoryRequest } from '@/api/client'
import type { InventoryData } from '@/api/contracts'
import { DashboardShell, type DashboardSection } from '@/components/gate-one/dashboard-shell'
import { InventoryDetailSheet } from '@/components/inventory/inventory-detail-sheet'
import { ProductSearchDialog, type ProductSearchItem } from '@/components/gate-two/product-search-dialog'
import { WorkspaceSession, type WorkspaceSessionValue } from '@/components/workspace-session'
import { useDebounce } from '@/hooks/use-debounce'
import '@/styles/inventory.css'

const PAGE_SIZE = 25
type InventoryRow = InventoryData['items'][number]
type SortBy = 'name' | 'sku'
type ProductForDetail = { product_id: number; name: string; sku: string; reference: string | false; category: string }

function number(value: number) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value)
}

function statusLabel(status: InventoryRow['status']) {
  if (status === 'out_of_stock') return 'Out of stock'
  if (status === 'low_stock') return 'Low stock'
  return 'In stock'
}

function StockStatus({ status }: { status: InventoryRow['status'] }) {
  return <span className={'inventory-status is-' + status}><span aria-hidden="true" />{statusLabel(status)}</span>
}

function InventorySummary({ data }: { data: InventoryData }) {
  const summary = data.summary
  const note = summary.complete
    ? 'Company-wide across tracked parts'
    : 'Based on ' + number(summary.sampled_products) + ' of ' + number(summary.total_tracked) + ' tracked parts'
  const metrics = [
    { label: 'Tracked parts', value: summary.total_tracked, note, tone: 'violet', icon: Boxes },
    { label: 'In stock', value: summary.in_stock, note: 'Above the set stock level', tone: 'green', icon: PackageSearch },
    { label: 'Low stock', value: summary.low_stock, note: 'At or below the set stock level', tone: 'amber', icon: ArrowDown },
    { label: 'Out of stock', value: summary.out_of_stock, note: 'No stock across the company', tone: 'red', icon: AlertCircle },
  ]
  return (
    <>
      <div className="inventory-summary-grid" aria-label="Company-wide inventory summary">
        {metrics.map(({ label, value, note: metricNote, tone, icon: Icon }) => (
          <article className={'inventory-summary-card tone-' + tone} key={label}>
            <span className="inventory-summary-icon"><Icon size={17} aria-hidden="true" /></span>
            <div className="inventory-summary-copy">
              <span>{label}</span>
              <strong>{number(value)}</strong>
              <small>{metricNote}</small>
            </div>
          </article>
        ))}
      </div>
      {!summary.complete && (
        <p className="inventory-summary-caveat" role="note">
          <CircleHelp size={14} aria-hidden="true" /> Summary coverage is limited by the current company catalog size.
        </p>
      )}
    </>
  )
}

function LoadingInventory() {
  return (
    <div className="inventory-loading panel" role="status" aria-label="Loading inventory">
      <span className="inventory-loading-title" />
      <span className="inventory-loading-row" />
      <span className="inventory-loading-row" />
      <span className="inventory-loading-row" />
      <span className="sr-only">Loading parts from your company inventory…</span>
    </div>
  )
}

function InventoryError({ error, onRetry }: { error: Error; onRetry: () => void }) {
  const forbidden = error instanceof ApiError && error.code === 'forbidden'
  return (
    <section className="inventory-state panel" role="alert">
      <span className="inventory-state-icon is-error"><AlertCircle size={21} aria-hidden="true" /></span>
      <h2>{forbidden ? 'Inventory access is restricted' : 'Inventory could not be loaded'}</h2>
      <p>{forbidden ? 'Your current role cannot read this company’s product inventory. Ask your administrator to review your inventory access.' : error.message}</p>
      {!forbidden && <button className="inventory-secondary-button" type="button" onClick={onRetry}>Try again</button>}
    </section>
  )
}

function EmptyInventory({ emptyCatalog, filtered, onReset }: { emptyCatalog: boolean; filtered: boolean; onReset: () => void }) {
  const title = emptyCatalog ? 'Your inventory is ready for its first parts' : 'No parts match these filters'
  const description = emptyCatalog
    ? 'Once storable products are added to this company, their stock and supplier details will appear here.'
    : 'Try a different search or clear one or more filters to see matching parts.'
  return (
    <section className="inventory-state panel" aria-live="polite">
      <span className="inventory-state-icon"><PackageSearch size={22} aria-hidden="true" /></span>
      <h2>{title}</h2>
      <p>{description}</p>
      {filtered && <button className="inventory-secondary-button" type="button" onClick={onReset}>Clear filters</button>}
    </section>
  )
}

function warehouseSummary(item: InventoryRow, warehouseFilter: number | undefined) {
  if (!item.warehouses.length) return warehouseFilter ? 'No stock here' : 'No current stock'
  if (warehouseFilter) {
    const selected = item.warehouses.find((warehouse) => warehouse.id === warehouseFilter)
    return selected ? number(selected.on_hand) + ' on hand' : 'No stock here'
  }
  return item.warehouses.slice(0, 2).map((warehouse) => warehouse.name + ' · ' + number(warehouse.on_hand)).join(' / ')
    + (item.warehouse_count > 2 ? ' +' + (item.warehouse_count - 2) : '')
}

function WarehouseCell({ item, warehouseFilter }: { item: InventoryRow; warehouseFilter?: number }) {
  if (!item.warehouses.length) {
    return <span className="inventory-warehouse-empty">{warehouseSummary(item, warehouseFilter)}</span>
  }
  if (warehouseFilter) return <span className="inventory-warehouse-value">{warehouseSummary(item, warehouseFilter)}</span>
  return (
    <div className="inventory-warehouse-chips" title={item.warehouses.map((warehouse) => warehouse.name + ': ' + number(warehouse.on_hand)).join(', ')}>
      {item.warehouses.slice(0, 2).map((warehouse) => (
        <span key={warehouse.id}><Warehouse size={12} aria-hidden="true" />{warehouse.name} <strong>{number(warehouse.on_hand)}</strong></span>
      ))}
      {item.warehouse_count > 2 && <small>+{item.warehouse_count - 2} more</small>}
    </div>
  )
}

function SupplierValue({ item }: { item: InventoryRow }) {
  if (item.supplier) {
    return (
      <span className="inventory-supplier-value">
        <strong>{item.supplier.name}</strong>
        <small>{item.supplier.lead_time_days} day{item.supplier.lead_time_days === 1 ? '' : 's'} lead time</small>
      </span>
    )
  }
  if (item.supplier_access_note) return <span className="inventory-muted-value">Restricted</span>
  if (item.supplier_lookup_limited) return <span className="inventory-muted-value">Supplier lookup limited</span>
  return <span className="inventory-muted-value">No supplier on file</span>
}

function MobileInventoryCard({ item, warehouseFilter, onOpen }: {
  item: InventoryRow
  warehouseFilter?: number
  onOpen: () => void
}) {
  return (
    <button className="inventory-mobile-card" type="button" onClick={onOpen} aria-label={'View stock details for ' + item.name}>
      <span className="inventory-mobile-top">
        <span className="inventory-mobile-identity">
          <strong>{item.name}</strong>
          <small>SKU {item.sku}{item.reference ? ' · OEM ' + item.reference : ''}</small>
        </span>
        <StockStatus status={item.status} />
      </span>
      <span className="inventory-mobile-stocks">
        <span>On hand <strong>{number(item.on_hand)} {item.uom}</strong></span>
        <span>Available to use <strong>{number(item.available)} {item.uom}</strong></span>
        <span>Incoming <strong>{number(item.incoming)} {item.uom}</strong></span>
      </span>
      <span className="inventory-mobile-meta">
        <span>{warehouseSummary(item, warehouseFilter)}</span>
        <span>{item.supplier ? item.supplier.name : item.supplier_access_note ? 'Supplier restricted' : 'No supplier on file'}</span>
      </span>
    </button>
  )
}

function InventoryPageContent({
  session, companyId, onSwitchCompany, onSignOut,
}: WorkspaceSessionValue) {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [selectedProduct, setSelectedProduct] = useState<ProductForDetail | null>(null)
  const [query, setQuery] = useState('')
  const [supplierQuery, setSupplierQuery] = useState('')
  const [status, setStatus] = useState<InventoryRequest['status']>('all')
  const [warehouseId, setWarehouseId] = useState<number | undefined>()
  const [categoryId, setCategoryId] = useState<number | undefined>()
  const [tracked, setTracked] = useState<InventoryRequest['tracked']>('all')
  const [active, setActive] = useState<InventoryRequest['active']>('active')
  const [sort, setSort] = useState<SortBy>('name')
  const [direction, setDirection] = useState<'asc' | 'desc'>('asc')
  const [page, setPage] = useState(1)
  const debouncedQuery = useDebounce(query.trim(), 250)
  const debouncedSupplier = useDebounce(supplierQuery.trim(), 250)
  const navigate = useNavigate()

  const options = useQuery({
    queryKey: ['inventory-options', companyId, debouncedSupplier],
    queryFn: () => api.inventoryOptions(companyId, debouncedSupplier),
  })
  const request: InventoryRequest = {
    query: debouncedQuery,
    supplierQuery: debouncedSupplier,
    status,
    warehouseId,
    categoryId,
    tracked,
    active,
    sort,
    direction,
    page,
    pageSize: PAGE_SIZE,
  }
  const inventory = useQuery({
    queryKey: ['inventory', companyId, request],
    queryFn: () => api.inventory(companyId, request),
    placeholderData: keepPreviousData,
  })
  const data = inventory.data
  const isFiltered = Boolean(debouncedQuery || debouncedSupplier || status !== 'all' || warehouseId || categoryId || tracked !== 'all' || active !== 'active')
  const activeWarehouseName = options.data?.warehouses.find((warehouse) => warehouse.id === warehouseId)?.name
  const stockScope = activeWarehouseName ? 'Company totals · ' + activeWarehouseName + ' view' : 'Company-wide stock totals'

  const openProduct = useCallback((item: InventoryRow) => {
    setSelectedProduct({
      product_id: item.product_id,
      name: item.name,
      sku: item.sku,
      reference: item.reference,
      category: item.category,
    })
  }, [])

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
    if (section === 'suppliers') void navigate({ to: '/suppliers' })
    if (section === 'forecast') void navigate({ to: '/' })
  }

  function clearFilters() {
    setQuery('')
    setSupplierQuery('')
    setStatus('all')
    setWarehouseId(undefined)
    setCategoryId(undefined)
    setTracked('all')
    setActive('active')
    setSort('name')
    setDirection('asc')
    setPage(1)
  }

  function onSearchProduct(product: ProductSearchItem) {
    setSelectedProduct({
      product_id: product.id,
      name: product.name,
      sku: product.sku,
      reference: product.reference,
      category: product.category,
    })
    setSearchOpen(false)
  }

  function onSortChange(value: string) {
    const nextSort = value as SortBy
    if (sort === nextSort) setDirection((current) => current === 'asc' ? 'desc' : 'asc')
    else {
      setSort(nextSort)
      setDirection('asc')
    }
    setPage(1)
  }

  const company = session.allowed_companies.find((item) => item.id === companyId) ?? session.current_company

  return (
    <>
      <DashboardShell
        collapsed={collapsed}
        onToggleCollapsed={() => setCollapsed((value) => !value)}
        activeSection="inventory"
        onNavigate={navigateTo}
        onUnavailable={() => undefined}
        onOpenSearch={() => setSearchOpen(true)}
        mobileNavOpen={mobileNavOpen}
        onMobileNavChange={setMobileNavOpen}
        session={session}
        companyId={companyId}
        onSwitchCompany={onSwitchCompany}
        onSignOut={onSignOut}
      >
        <main className="page-content inventory-page" id="inventory-top">
          <div className="page-heading inventory-page-heading">
            <div>
              <div className="inventory-eyebrow"><Boxes size={14} aria-hidden="true" /> Parts and stock</div>
              <h1>Inventory</h1>
              <p>Find parts, check available stock, and see where each item is held at {company.name}.</p>
            </div>
            <button className="inventory-search-button" type="button" onClick={() => setSearchOpen(true)} aria-label="Open global part search">
              <Search size={16} aria-hidden="true" /><span>Search all parts</span><kbd>Ctrl K</kbd>
            </button>
          </div>

          {inventory.isError && !data ? (
            <InventoryError error={inventory.error} onRetry={() => void inventory.refetch()} />
          ) : inventory.isPending && !data ? (
            <LoadingInventory />
          ) : data ? (
            <>
              <InventorySummary data={data} />
              <section className="inventory-catalog panel" aria-labelledby="inventory-catalog-title">
                <div className="inventory-catalog-heading">
                  <div className="inventory-catalog-title">
                    <span className="inventory-catalog-icon"><PackageSearch size={18} aria-hidden="true" /></span>
                    <div>
                      <h2 id="inventory-catalog-title">Parts catalog</h2>
                      <p>{stockScope} · quantities reflect current stock records</p>
                    </div>
                  </div>
                  <span className="inventory-live-mark"><i aria-hidden="true" /> Current stock</span>
                </div>

                <div className="inventory-filter-area">
                  <label className="inventory-search-field">
                    <Search size={16} aria-hidden="true" />
                    <span className="sr-only">Search by part name, SKU, OEM reference, or supplier</span>
                    <input
                      value={query}
                      onChange={(event) => { setQuery(event.target.value); setPage(1) }}
                      placeholder="Search name, SKU, OEM reference, or supplier…"
                      type="search"
                      autoComplete="off"
                    />
                    {query && <button type="button" aria-label="Clear part search" onClick={() => { setQuery(''); setPage(1) }}>Clear</button>}
                  </label>
                  <div className="inventory-filters">
                    <label className="inventory-select-wrap">
                      <span>Status</span>
                      <select aria-label="Filter by stock status" value={status} onChange={(event) => { setStatus(event.target.value as InventoryRequest['status']); setPage(1) }}>
                        <option value="all">All statuses</option>
                        <option value="in_stock">In stock</option>
                        <option value="low_stock">Low stock</option>
                        <option value="out_of_stock">Out of stock</option>
                      </select>
                    </label>
                    <label className="inventory-select-wrap inventory-filter-warehouse">
                      <span>Warehouse</span>
                      <select aria-label="Filter by warehouse" value={warehouseId ?? ''} onChange={(event) => { setWarehouseId(event.target.value ? Number(event.target.value) : undefined); setPage(1) }} disabled={options.isPending}>
                        <option value="">All warehouses</option>
                        {options.data?.warehouses.map((warehouse) => <option key={warehouse.id} value={warehouse.id}>{warehouse.name}</option>)}
                      </select>
                    </label>
                    <label className="inventory-select-wrap">
                      <span>Category</span>
                      <select aria-label="Filter by category" value={categoryId ?? ''} onChange={(event) => { setCategoryId(event.target.value ? Number(event.target.value) : undefined); setPage(1) }} disabled={options.isPending}>
                        <option value="">All categories</option>
                        {options.data?.categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
                      </select>
                    </label>
                    <label className="inventory-select-wrap inventory-filter-tracked">
                      <span>Monitoring</span>
                      <select aria-label="Filter by AutoStock monitoring" value={tracked} onChange={(event) => { setTracked(event.target.value as InventoryRequest['tracked']); setPage(1) }}>
                        <option value="all">All parts</option>
                        <option value="tracked">Monitored</option>
                        <option value="not_tracked">Not monitored</option>
                      </select>
                    </label>
                    <label className="inventory-select-wrap inventory-filter-active">
                      <span>Part status</span>
                      <select aria-label="Filter by active or archived parts" value={active} onChange={(event) => { setActive(event.target.value as InventoryRequest['active']); setPage(1) }}>
                        <option value="active">Active</option>
                        <option value="archived">Archived</option>
                        <option value="all">Active and archived</option>
                      </select>
                    </label>
                  </div>
                  {options.data?.supplier_access ? (
                    <label className="inventory-supplier-filter">
                      <span>Supplier</span>
                      <input
                        value={supplierQuery}
                        onChange={(event) => { setSupplierQuery(event.target.value); setPage(1) }}
                        placeholder="Filter by supplier name"
                        list="inventory-supplier-options"
                        autoComplete="off"
                      />
                      <datalist id="inventory-supplier-options">
                        {options.data.suppliers.map((supplier) => <option key={supplier.id} value={supplier.name} />)}
                      </datalist>
                    </label>
                  ) : options.data && (
                    <p className="inventory-permission-note"><CircleHelp size={14} aria-hidden="true" /> Supplier filtering is unavailable for your role.</p>
                  )}
                </div>

                {options.isError && <p className="inventory-options-note" role="status">Some filter choices could not be loaded. Search and stock status filters remain available.</p>}
                {options.data?.supplier_options_limited && <p className="inventory-options-note">Supplier suggestions are limited. You can still type a supplier name to filter the full catalog.</p>}
                {options.data?.category_options_limited && <p className="inventory-options-note">Showing the first available categories; use search to find other parts.</p>}
                {options.data?.warehouse_options_limited && <p className="inventory-options-note">Showing the first 50 warehouses. Company-wide totals remain complete.</p>}

                <div className="inventory-results-bar">
                  <div>
                    <strong>{number(data.pagination.total_count)}</strong>
                    <span>{data.pagination.total_count === 1 ? 'part' : 'parts'}{isFiltered ? ' match your filters' : ' in this view'}</span>
                    {inventory.isFetching && <span className="inventory-refreshing" role="status">Updating…</span>}
                  </div>
                  <div className="inventory-results-actions">
                    {isFiltered && <button className="inventory-reset-button" type="button" onClick={clearFilters}><Filter size={13} aria-hidden="true" />Clear filters</button>}
                    <label className="inventory-sort-control">
                      <span>Sort</span>
                      <select aria-label="Sort parts by" value={sort} onChange={(event) => onSortChange(event.target.value)}>
                        <option value="name">Part name</option>
                        <option value="sku">SKU</option>
                      </select>
                      <button type="button" aria-label={'Sort ' + sort + ' ' + (direction === 'asc' ? 'descending' : 'ascending')} onClick={() => setDirection((current) => current === 'asc' ? 'desc' : 'asc')}>
                        {direction === 'asc' ? <ArrowDown size={13} aria-hidden="true" /> : <ArrowUp size={13} aria-hidden="true" />}
                      </button>
                    </label>
                  </div>
                </div>

                {inventory.isError ? (
                  <div className="inventory-inline-error" role="alert">
                    <AlertCircle size={16} aria-hidden="true" /><span>{inventory.error.message}</span>
                    <button type="button" onClick={() => void inventory.refetch()}>Retry</button>
                  </div>
                ) : inventory.isFetching && !data.items.length ? (
                  <div className="inventory-table-loading" role="status">Loading matching parts…</div>
                ) : data.items.length === 0 ? (
                  <EmptyInventory emptyCatalog={data.empty_catalog} filtered={isFiltered} onReset={clearFilters} />
                ) : (
                  <>
                    <div className="inventory-table-wrap">
                      <table className="inventory-table">
                        <thead>
                          <tr>
                            <th scope="col" className="inventory-col-part">Part</th>
                            <th scope="col" className="inventory-col-sku">SKU</th>
                            <th scope="col" className="inventory-col-number" title="Physical units currently in stock">On hand <span>physical stock</span></th>
                            <th scope="col" className="inventory-col-number" title="On-hand units that are not reserved">Available <span>not reserved</span></th>
                            <th scope="col" className="inventory-col-incoming">Incoming <span>company</span></th>
                            <th scope="col" className="inventory-col-warehouse">Warehouse stock</th>
                            <th scope="col" className="inventory-col-supplier">Supplier</th>
                            <th scope="col" className="inventory-col-status">Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.items.map((item) => (
                            <tr key={item.product_id} data-testid="inventory-row">
                              <td className="inventory-cell-part">
                                <button type="button" className="inventory-part-link" onClick={() => openProduct(item)} aria-label={'Open details for ' + item.name}>
                                  <span className="inventory-part-icon"><PackageSearch size={16} aria-hidden="true" /></span>
                                  <span className="inventory-part-copy"><strong>{item.name}</strong><small>{item.category}{item.reference ? ' · OEM ' + item.reference : ''}</small></span>
                                </button>
                              </td>
                              <td className="inventory-col-sku inventory-cell-sku">{item.sku}</td>
                              <td className="inventory-cell-quantity"><strong>{number(item.on_hand)}</strong><small>{item.uom}</small></td>
                              <td className="inventory-cell-quantity"><strong>{number(item.available)}</strong><small>{item.uom}</small></td>
                              <td className="inventory-col-incoming inventory-cell-quantity"><strong>{number(item.incoming)}</strong><small>{item.uom}</small></td>
                              <td className="inventory-col-warehouse inventory-cell-warehouse"><WarehouseCell item={item} warehouseFilter={warehouseId} /></td>
                              <td className="inventory-col-supplier inventory-cell-supplier"><SupplierValue item={item} /></td>
                              <td className="inventory-cell-status"><StockStatus status={item.status} /></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div className="inventory-mobile-list">
                      {data.items.map((item) => <MobileInventoryCard key={item.product_id} item={item} warehouseFilter={warehouseId} onOpen={() => openProduct(item)} />)}
                    </div>
                    <div className="inventory-pagination">
                      <span>Showing <strong>{number((data.pagination.page - 1) * data.pagination.page_size + 1)}–{number(Math.min(data.pagination.page * data.pagination.page_size, data.pagination.total_count))}</strong> of <strong>{number(data.pagination.total_count)}</strong></span>
                      <div>
                        <button type="button" aria-label="Previous page" disabled={!data.pagination.has_previous || inventory.isFetching} onClick={() => setPage((value) => Math.max(1, value - 1))}><ChevronLeft size={16} aria-hidden="true" />Previous</button>
                        <span>Page {data.pagination.page} of {data.pagination.total_pages}</span>
                        <button type="button" aria-label="Next page" disabled={!data.pagination.has_next || inventory.isFetching} onClick={() => setPage((value) => value + 1)}>Next<ChevronRight size={16} aria-hidden="true" /></button>
                      </div>
                    </div>
                    {data.pagination.status_scan_used && <p className="inventory-coverage-note">Stock status was checked across the matching server-side catalog before paging.</p>}
                    {data.coverage.supplier_lines_limited && <p className="inventory-coverage-note">Supplier terms are too extensive to summarize for every listed part. Open a part for its available details.</p>}
                  </>
                )}
              </section>
              <p className="inventory-page-footnote">Stock quantities are company-wide unless a warehouse is selected. Selecting a warehouse changes the warehouse view and stock-status filter.</p>
            </>
          ) : null}
        </main>
      </DashboardShell>
      <ProductSearchDialog open={searchOpen} onOpenChange={setSearchOpen} companyId={companyId} onSelectProduct={onSearchProduct} />
      <InventoryDetailSheet
        product={selectedProduct}
        companyId={companyId}
        warehouseId={warehouseId}
        locale={session.user.locale}
        timezone={session.user.timezone}
        onClose={() => setSelectedProduct(null)}
      />
    </>
  )
}

export function InventoryPage() {
  return <WorkspaceSession>{(workspace) => <InventoryPageContent {...workspace} key={workspace.companyId} />}</WorkspaceSession>
}
