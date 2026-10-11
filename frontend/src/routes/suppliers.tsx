import { useEffect, useState, type ReactNode } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import {
  AlertCircle, ArrowDown, ArrowUp, Building2, Check, ChevronLeft, ChevronRight,
  CircleHelp, Clock3, FileText, Mail, MapPin, PackageSearch, Phone, Search,
  ShieldCheck, Truck,
} from 'lucide-react'
import { ApiError, api, type SupplierPartsRequest, type SupplierRequest } from '@/api/client'
import type { SupplierData, SupplierDetailData, SupplierPartsData, SupplierTermsData } from '@/api/contracts'
import { DashboardShell, type DashboardSection } from '@/components/gate-one/dashboard-shell'
import { InventoryDetailSheet } from '@/components/inventory/inventory-detail-sheet'
import { ProductSearchDialog, type ProductSearchItem } from '@/components/gate-two/product-search-dialog'
import { WorkspaceSession, type WorkspaceSessionValue } from '@/components/workspace-session'
import { useDebounce } from '@/hooks/use-debounce'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import '@/styles/inventory.css'
import '@/styles/warehouses.css'
import '@/styles/suppliers.css'

const SUPPLIER_PAGE_SIZE = 12
const PART_PAGE_SIZE = 25
type SupplierRow = SupplierData['suppliers'][number]
type SupplierPart = SupplierPartsData['items'][number]
type ProductStub = Pick<ProductSearchItem, 'id' | 'name' | 'sku' | 'reference' | 'category'>
type PartStatus = SupplierPartsRequest['status']

function count(value: number | false) {
  return value === false ? '—' : new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value)
}

function quantity(value: number, uom: string) {
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value)} ${uom}`
}

function leadRange(min: number | false, max: number | false) {
  if (min === false || max === false) return 'Not provided'
  return min === max ? `${min} days` : `${min}–${max} days`
}

function statusName(status: SupplierPart['status']) {
  if (status === 'out_of_stock') return 'Out of stock'
  if (status === 'low_stock') return 'Low stock'
  return 'In stock'
}

function StockStatus({ status }: { status: SupplierPart['status'] }) {
  return <span className={`inventory-status is-${status}`}><i aria-hidden="true" />{statusName(status)}</span>
}

function SupplierError({ error, onRetry, detail = false }: { error: Error; onRetry: () => void; detail?: boolean }) {
  const forbidden = error instanceof ApiError && error.code === 'forbidden'
  return (
    <section className="inventory-state panel" role="alert">
      <span className="inventory-state-icon is-error"><AlertCircle size={21} aria-hidden="true" /></span>
      <h2>{forbidden ? 'Supplier information is restricted' : `${detail ? 'Supplier details' : 'Suppliers'} could not be loaded`}</h2>
      <p>{forbidden ? 'Your current role cannot read supplier and inventory information for this company. Ask your administrator to review your access.' : error.message}</p>
      {!forbidden && <button className="inventory-secondary-button" type="button" onClick={onRetry}>Try again</button>}
    </section>
  )
}

function SupplierLoading({ detail = false }: { detail?: boolean }) {
  return <section className="supplier-loading panel" role="status" aria-label={detail ? 'Loading supplier details' : 'Loading suppliers'}><span className="sr-only">Loading supplier information from your company…</span><i /><i /><i /></section>
}

function SupplierMetrics({ data }: { data: SupplierData }) {
  const summary = data.summary
  const metrics = [
    { label: 'Active suppliers', value: count(summary.active_suppliers), note: 'Available to this company', tone: 'violet', icon: Building2 },
    { label: 'Parts with supplier', value: count(summary.parts_with_supplier), note: 'At least one configured supplier', tone: 'green', icon: PackageSearch },
    { label: 'Parts missing supplier', value: count(summary.parts_missing_supplier), note: 'No supplier term on file', tone: 'amber', icon: AlertCircle },
    { label: 'With reorder needs', value: count(summary.suppliers_with_reorder_needs), note: 'Suppliers linked to current suggestions', tone: 'red', icon: Truck },
  ]
  return (
    <>
      <div className="inventory-summary-grid supplier-summary-grid" aria-label="Supplier overview">
        {metrics.map(({ label, value, note, tone, icon: Icon }) => <article className={`inventory-summary-card tone-${tone}`} key={label}>
          <span className="inventory-summary-icon"><Icon size={17} aria-hidden="true" /></span>
          <div className="inventory-summary-copy"><span>{label}</span><strong>{value}</strong><small>{note}</small></div>
        </article>)}
      </div>
      {data.coverage.note && <p className="inventory-summary-caveat" role="note"><CircleHelp size={14} aria-hidden="true" />{data.coverage.note}</p>}
    </>
  )
}

function leadRangeText(row: SupplierRow) {
  return leadRange(row.lead_time_min_days, row.lead_time_max_days)
}

function SupplierStatus({ row }: { row: SupplierRow }) {
  if (row.reorder_parts === false) return <span className="supplier-attention is-unknown"><CircleHelp size={13} aria-hidden="true" />Needs unavailable</span>
  if (row.reorder_parts > 0) return <span className="supplier-attention is-needed"><i aria-hidden="true" />{count(row.reorder_parts)} part{row.reorder_parts === 1 ? '' : 's'} to restock</span>
  return <span className="supplier-attention is-clear"><Check size={13} aria-hidden="true" />No current needs</span>
}

function SupplierListCard({ row }: { row: SupplierRow }) {
  return <Link className="supplier-card" to="/suppliers/$supplierId" params={{ supplierId: String(row.id) }} aria-label={`Open ${row.name} supplier details`}>
    <div className="supplier-card-heading">
      <span className="supplier-card-icon"><Building2 size={18} aria-hidden="true" /></span>
      <span className="supplier-card-name"><strong>{row.name}</strong><small>{row.vendor_code ? `Vendor code ${row.vendor_code}` : 'No vendor code'}{row.city ? ` · ${row.city}` : ''}</small></span>
      <ChevronRight size={17} aria-hidden="true" />
    </div>
    <div className="supplier-card-metrics">
      <span><small>Parts</small><strong>{count(row.active_parts)}</strong></span>
      <span><small>Low / out of stock</small><strong>{count(row.low_or_out_parts)}</strong></span>
      <span><small>Lead time</small><strong>{leadRangeText(row)}</strong></span>
      <span><small>Supplier terms</small><strong>{count(row.active_terms)}</strong></span>
    </div>
    <div className="supplier-card-foot"><SupplierStatus row={row} /><span>View supplier <ChevronRight size={14} aria-hidden="true" /></span></div>
  </Link>
}

function SupplierPagination({ page, pageSize = SUPPLIER_PAGE_SIZE, totalPages, totalCount, hasPrevious, hasNext, onPage }: {
  page: number; pageSize?: number; totalPages: number; totalCount: number; hasPrevious: boolean; hasNext: boolean; onPage: (page: number) => void
}) {
  const from = totalCount ? (page - 1) * pageSize + 1 : 0
  const to = Math.min(page * pageSize, totalCount)
  return <div className="supplier-pagination" aria-label="Supplier pages">
    <span>Showing {from}–{to} of {count(totalCount)}</span>
    <div><button type="button" disabled={!hasPrevious} onClick={() => onPage(page - 1)} aria-label="Previous page"><ChevronLeft size={16} /></button><span>Page {page} of {Math.max(1, totalPages)}</span><button type="button" disabled={!hasNext} onClick={() => onPage(page + 1)} aria-label="Next page"><ChevronRight size={16} /></button></div>
  </div>
}

function SupplierOverview({ companyId, session, onSwitchCompany, onSignOut }: WorkspaceSessionValue) {
  const [query, setQuery] = useState('')
  const [attention, setAttention] = useState<SupplierRequest['attention']>('all')
  const [terms, setTerms] = useState<SupplierRequest['terms']>('all')
  const [sort, setSort] = useState<SupplierRequest['sort']>('name')
  const [direction, setDirection] = useState<SupplierRequest['direction']>('asc')
  const [page, setPage] = useState(1)
  const [selectedProduct, setSelectedProduct] = useState<ProductStub | null>(null)
  const debouncedQuery = useDebounce(query.trim(), 250)
  const request: SupplierRequest = { query: debouncedQuery, attention, terms, sort, direction, page, pageSize: SUPPLIER_PAGE_SIZE }
  const suppliers = useQuery({ queryKey: ['suppliers', companyId, request], queryFn: () => api.suppliers(companyId, request), placeholderData: keepPreviousData })
  const company = session.allowed_companies.find((item) => item.id === companyId) ?? session.current_company

  function resetFilters() { setQuery(''); setAttention('all'); setTerms('all'); setSort('name'); setDirection('asc'); setPage(1) }

  return <SupplierWorkspace workspace={{ session, companyId, onSwitchCompany, onSignOut }} activeSection="suppliers" selectedProduct={selectedProduct} onSelectProduct={setSelectedProduct}>
    <main className="page-content inventory-page supplier-page">
      <div className="page-heading inventory-page-heading supplier-page-heading">
        <div><div className="inventory-eyebrow"><Building2 size={14} aria-hidden="true" /> Supplier relationships</div><h1>Suppliers</h1><p>See who supplies your parts, the terms you have on file, and suppliers connected to parts currently suggested for restocking at {company.name}.</p></div>
        <div className="supplier-heading-actions"><Link to="/suppliers/missing" className="supplier-primary-link"><PackageSearch size={15} aria-hidden="true" />Parts without a supplier</Link><span className="warehouse-readonly-mark"><ShieldCheck size={14} aria-hidden="true" /> Read-only view</span></div>
      </div>
      {suppliers.isError && !suppliers.data ? <SupplierError error={suppliers.error} onRetry={() => void suppliers.refetch()} /> : suppliers.isPending && !suppliers.data ? <SupplierLoading /> : suppliers.data ? <>
        <SupplierMetrics data={suppliers.data} />
        <section className="supplier-catalog panel" aria-labelledby="supplier-list-title">
          <div className="warehouse-section-heading supplier-list-heading"><div className="inventory-catalog-title"><span className="inventory-catalog-icon"><Building2 size={18} aria-hidden="true" /></span><div><h2 id="supplier-list-title">Your suppliers</h2><p>Current supplier terms and stock are scoped to {company.name}.</p></div></div><span className="inventory-live-mark"><i aria-hidden="true" /> Live Odoo data</span></div>
          <div className="supplier-filter-area">
            <label className="inventory-search-field"><Search size={16} aria-hidden="true" /><span className="sr-only">Search suppliers by name or vendor code</span><input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1) }} placeholder="Search supplier name or vendor code…" type="search" autoComplete="off" />{query && <button type="button" aria-label="Clear supplier search" onClick={() => { setQuery(''); setPage(1) }}>Clear</button>}</label>
            <div className="supplier-filters">
              <label className="inventory-select-wrap"><span>Current needs</span><select aria-label="Filter suppliers by parts to restock" value={attention} onChange={(event) => { setAttention(event.target.value as SupplierRequest['attention']); setPage(1) }}><option value="all">All suppliers</option><option value="reorder">With parts to restock</option></select></label>
              <label className="inventory-select-wrap"><span>Supplier terms</span><select aria-label="Filter suppliers by active terms" value={terms} onChange={(event) => { setTerms(event.target.value as SupplierRequest['terms']); setPage(1) }}><option value="all">All terms</option><option value="active">Active terms</option><option value="none">No active terms</option></select></label>
              <label className="inventory-select-wrap"><span>Sort by</span><select aria-label="Sort suppliers by" value={sort} onChange={(event) => { setSort(event.target.value as SupplierRequest['sort']); setPage(1) }}><option value="name">Name</option><option value="reorder">Parts to restock</option><option value="parts">Parts supplied</option><option value="lead_time">Lead time</option></select></label>
              <button className="supplier-direction" type="button" aria-label={`Sort ${direction === 'asc' ? 'descending' : 'ascending'}`} onClick={() => { setDirection((value) => value === 'asc' ? 'desc' : 'asc'); setPage(1) }}>{direction === 'asc' ? <ArrowUp size={15} /> : <ArrowDown size={15} />}</button>
            </div>
          </div>
          {suppliers.data.suppliers.length ? <>
            <div className="supplier-table-wrap"><table className="supplier-table"><thead><tr><th>Supplier</th><th>Parts supplied</th><th>Low / out of stock</th><th>Parts to restock</th><th>Lead-time range</th><th>Active terms</th><th><span className="sr-only">Details</span></th></tr></thead><tbody>{suppliers.data.suppliers.map((row) => <tr key={row.id}>
              <td><Link to="/suppliers/$supplierId" params={{ supplierId: String(row.id) }} className="supplier-table-name"><span className="supplier-table-icon"><Building2 size={16} aria-hidden="true" /></span><span><strong>{row.name}</strong><small>{row.vendor_code ? `Vendor code ${row.vendor_code}` : row.city || 'Supplier'}</small></span></Link></td>
              <td>{count(row.active_parts)} <small>parts</small></td><td>{count(row.low_or_out_parts)}</td><td><SupplierStatus row={row} /></td><td>{leadRangeText(row)}</td><td>{count(row.active_terms)} <small>terms</small></td><td><Link to="/suppliers/$supplierId" params={{ supplierId: String(row.id) }} className="supplier-open-link">Details <ChevronRight size={14} /></Link></td>
            </tr>)}</tbody></table></div>
            <div className="supplier-mobile-list">{suppliers.data.suppliers.map((row) => <SupplierListCard key={row.id} row={row} />)}</div>
            <SupplierPagination page={suppliers.data.pagination.page} totalPages={suppliers.data.pagination.total_pages} totalCount={suppliers.data.pagination.total_count} hasPrevious={suppliers.data.pagination.has_previous} hasNext={suppliers.data.pagination.has_next} onPage={setPage} />
          </> : <section className="supplier-empty"><span className="inventory-state-icon"><PackageSearch size={22} aria-hidden="true" /></span><h2>{query || attention !== 'all' || terms !== 'all' ? 'No suppliers match these filters' : 'No suppliers are configured yet'}</h2><p>{query || attention !== 'all' || terms !== 'all' ? 'Try a different name or clear the filters to see suppliers available to this company.' : 'Once supplier records or vendor terms are added in Odoo, their parts and terms will appear here.'}</p>{(query || attention !== 'all' || terms !== 'all') && <button className="inventory-secondary-button" type="button" onClick={resetFilters}>Clear filters</button>}</section>}
          {suppliers.isFetching && <div className="warehouse-fetching" role="status">Updating supplier results…</div>}
        </section>
      </> : null}
    </main>
  </SupplierWorkspace>
}

function ContactDetails({ supplier }: { supplier: SupplierDetailData['supplier'] }) {
  const location = [supplier.city, supplier.country].filter(Boolean).join(', ')
  if (!supplier.email && !supplier.phone && !location) return <p className="supplier-contact-empty">No business contact details are on file.</p>
  return <div className="supplier-contact-list">
    {supplier.email && <span><Mail size={14} aria-hidden="true" />{supplier.email}</span>}
    {supplier.phone && <span><Phone size={14} aria-hidden="true" />{supplier.phone}</span>}
    {location && <span><MapPin size={14} aria-hidden="true" />{location}</span>}
  </div>
}

function ReorderContext({ item }: { item: SupplierPart }) {
  if (!item.reorder_parts) return <span className="supplier-reorder-none">No current suggestion</span>
  const first = item.reorder_locations[0]
  if (!first) return <span className="supplier-reorder-unknown"><CircleHelp size={13} aria-hidden="true" />Suggestion details unavailable</span>
  return <span className="supplier-reorder-chip"><Truck size={13} aria-hidden="true" />{first.warehouse}: {quantity(first.quantity, first.uom)} suggested{item.reorder_locations.length > 1 ? ` +${item.reorder_locations.length - 1} locations` : ''}</span>
}

function SupplierPartCard({ item, onOpenProduct, onOpenTerms }: { item: SupplierPart; onOpenProduct: () => void; onOpenTerms: () => void }) {
  return <article className="supplier-part-card">
    <div className="supplier-part-card-heading"><button className="supplier-part-name" type="button" onClick={onOpenProduct}><strong>{item.name}</strong><small>{item.sku} {item.reference ? `· ${item.reference}` : ''}</small></button><StockStatus status={item.status} /></div>
    <div className="supplier-part-card-values"><span><small>On hand</small><strong>{quantity(item.on_hand, item.uom)}</strong></span><span><small>Available to use</small><strong>{quantity(item.available, item.uom)}</strong></span><span><small>Lead-time range</small><strong>{leadRange(item.lead_time_min_days, item.lead_time_max_days)}</strong></span></div>
    <div className="supplier-part-card-foot"><ReorderContext item={item} /><button className="supplier-terms-button" type="button" onClick={onOpenTerms}><FileText size={14} aria-hidden="true" />View terms ({item.supplier_terms_count})</button></div>
  </article>
}

function PartTermsSheet({ companyId, supplierId, product, open, onOpenChange }: {
  companyId: number; supplierId: number; product: ProductStub | null; open: boolean; onOpenChange: (open: boolean) => void
}) {
  const termsQuery = useQuery({
    queryKey: ['supplier-terms', companyId, supplierId, product?.id],
    queryFn: () => api.supplierTerms(companyId, supplierId, product!.id),
    enabled: open && Boolean(product),
  })
  const data: SupplierTermsData | undefined = termsQuery.data
  return <Sheet open={open} onOpenChange={onOpenChange}>
    <SheetContent side="right" className="supplier-terms-sheet">
      <SheetHeader className="supplier-terms-sheet-heading"><span className="supplier-terms-icon"><FileText size={18} aria-hidden="true" /></span><SheetTitle>{data?.product.name ?? product?.name ?? 'Supplier terms'}</SheetTitle><SheetDescription>{data ? `${data.supplier.name} · SKU ${data.product.sku}` : 'Vendor prices, quantity breaks, and delivery terms on file.'}</SheetDescription></SheetHeader>
      {termsQuery.isError ? <div className="supplier-sheet-state" role="alert"><AlertCircle size={19} aria-hidden="true" /><strong>Terms could not be loaded</strong><p>{termsQuery.error.message}</p><button className="inventory-secondary-button" type="button" onClick={() => void termsQuery.refetch()}>Try again</button></div> : termsQuery.isPending ? <div className="supplier-sheet-state" role="status">Loading vendor terms…</div> : data ? <div className="supplier-terms-list">
        <p className="supplier-terms-intro">Each row is a separate Odoo vendor term. Quantity breaks, minimum order quantities, currencies, and company scope are shown as configured.</p>
        {data.terms.map((term) => <article className={`supplier-term-card${term.active_today ? '' : ' is-inactive'}`} key={term.id}>
          <div className="supplier-term-top"><div><strong>{term.vendor_product_name || data.product.name}</strong><small>{term.vendor_product_code ? `Vendor code ${term.vendor_product_code}` : 'No vendor part code'}</small></div><span className={`supplier-term-state${term.active_today ? ' is-active' : ''}`}>{term.active_today ? 'Current term' : 'Not current today'}</span></div>
          <div className="supplier-term-price"><span>Configured price</span><strong>{term.price_available ? `${term.currency.symbol} ${new Intl.NumberFormat(undefined, { minimumFractionDigits: term.currency.decimal_places, maximumFractionDigits: term.currency.decimal_places }).format(term.price as number)} ${term.currency.code}` : 'Price not provided'}</strong></div>
          <dl><div><dt>Price applies from</dt><dd>{quantity(term.price_break_min_qty, term.price_break_uom)}</dd></div><div><dt>Minimum order</dt><dd>{term.minimum_order_qty ? quantity(term.minimum_order_qty, term.minimum_order_uom) : 'Not specified'}</dd></div><div><dt>Lead time</dt><dd>{term.lead_time_days} days</dd></div><div><dt>Term scope</dt><dd>{term.company_id ? 'Company-specific' : 'Shared across companies'}</dd></div><div><dt>Valid from</dt><dd>{term.valid_from || 'No start date'}</dd></div><div><dt>Valid until</dt><dd>{term.valid_until || 'No end date'}</dd></div></dl>
        </article>)}
        {!data.terms.length && <p className="supplier-sheet-state">No supplier terms are visible for this part.</p>}
        {data.terms_truncated && <p className="supplier-terms-note" role="note">More than the safe display limit of terms are configured. The first {data.terms.length} sequence-ordered terms are shown.</p>}
      </div> : null}
    </SheetContent>
  </Sheet>
}

function SupplierPartTable({ companyId, supplierId, query, setQuery, status, setStatus, page, setPage, onSelectProduct }: {
  companyId: number; supplierId: number; query: string; setQuery: (value: string) => void; status: PartStatus; setStatus: (value: PartStatus) => void; page: number; setPage: (value: number) => void; onSelectProduct: (product: ProductStub) => void
}) {
  const debouncedQuery = useDebounce(query.trim(), 250)
  const request: SupplierPartsRequest = { query: debouncedQuery, status, sort: 'name', direction: 'asc', page, pageSize: PART_PAGE_SIZE }
  const partsQuery = useQuery({ queryKey: ['supplier-parts', companyId, supplierId, request], queryFn: () => api.supplierParts(companyId, supplierId, request), placeholderData: keepPreviousData })
  const data = partsQuery.data
  const [termsProduct, setTermsProduct] = useState<ProductStub | null>(null)

  function productStub(item: SupplierPart): ProductStub {
    return { id: item.product_id, name: item.name, sku: item.sku, reference: item.reference, category: item.category }
  }

  return <>
    <section className="supplier-parts-panel panel" aria-labelledby="supplier-parts-title">
      <div className="supplier-section-heading"><div><h2 id="supplier-parts-title">Parts supplied</h2><p>Stock is current company stock. Quantities keep each part’s own unit.</p></div><span className="inventory-live-mark"><i aria-hidden="true" /> Current stock</span></div>
      <div className="supplier-filter-area supplier-parts-filter-area">
        <label className="inventory-search-field"><Search size={16} aria-hidden="true" /><span className="sr-only">Search this supplier's parts by name, SKU, or reference</span><input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1) }} placeholder="Search parts, SKU, or OEM reference…" type="search" autoComplete="off" />{query && <button type="button" aria-label="Clear part search" onClick={() => { setQuery(''); setPage(1) }}>Clear</button>}</label>
        <label className="inventory-select-wrap"><span>Stock status</span><select aria-label="Filter supplier parts by stock status" value={status} onChange={(event) => { setStatus(event.target.value as PartStatus); setPage(1) }}><option value="all">All parts</option><option value="in_stock">In stock</option><option value="low_stock">Low stock</option><option value="out_of_stock">Out of stock</option></select></label>
      </div>
      {partsQuery.isError && !data ? <SupplierError error={partsQuery.error} detail onRetry={() => void partsQuery.refetch()} /> : partsQuery.isPending && !data ? <div className="supplier-part-loading" role="status">Loading supplied parts…</div> : data?.items.length ? <>
        <div className="supplier-part-table-wrap"><table className="supplier-part-table"><thead><tr><th>Part</th><th>Stock status</th><th>On hand</th><th>Available to use</th><th>Suggested order</th><th>Vendor terms</th><th><span className="sr-only">Part actions</span></th></tr></thead><tbody>{data.items.map((item) => <tr key={item.product_id}>
          <td><button className="supplier-part-name" type="button" onClick={() => onSelectProduct(productStub(item))}><strong>{item.name}</strong><small>{item.sku}{item.reference ? ` · ${item.reference}` : ''}</small></button></td><td><StockStatus status={item.status} /></td><td>{quantity(item.on_hand, item.uom)}</td><td>{quantity(item.available, item.uom)}</td><td><ReorderContext item={item} /></td><td>{leadRange(item.lead_time_min_days, item.lead_time_max_days)}<small className="supplier-part-terms-count">{item.supplier_terms_count} configured term{item.supplier_terms_count === 1 ? '' : 's'}</small></td><td><button className="supplier-terms-button" type="button" onClick={() => setTermsProduct(productStub(item))}><FileText size={14} aria-hidden="true" />View terms</button></td>
        </tr>)}</tbody></table></div>
        <div className="supplier-part-mobile-list">{data.items.map((item) => <SupplierPartCard key={item.product_id} item={item} onOpenProduct={() => onSelectProduct(productStub(item))} onOpenTerms={() => setTermsProduct(productStub(item))} />)}</div>
        {!data.coverage.reorder_complete && <p className="inventory-summary-caveat supplier-parts-caveat" role="note"><CircleHelp size={14} aria-hidden="true" />Restock suggestions are incomplete because the company stock scan reached its safe review limit.</p>}
        <SupplierPagination page={data.pagination.page} pageSize={data.pagination.page_size} totalPages={data.pagination.total_pages} totalCount={data.pagination.total_count} hasPrevious={data.pagination.has_previous} hasNext={data.pagination.has_next} onPage={setPage} />
        {partsQuery.isFetching && <div className="warehouse-fetching" role="status">Updating part results…</div>}
      </> : <section className="supplier-empty"><span className="inventory-state-icon"><PackageSearch size={22} aria-hidden="true" /></span><h2>{query || status !== 'all' ? 'No parts match these filters' : 'No current parts are linked to this supplier'}</h2><p>{query || status !== 'all' ? 'Try another search or clear the stock filter.' : 'Current vendor terms will appear here when they are configured for active parts.'}</p>{(query || status !== 'all') && <button className="inventory-secondary-button" type="button" onClick={() => { setQuery(''); setStatus('all'); setPage(1) }}>Clear filters</button>}</section>}
    </section>
    <PartTermsSheet companyId={companyId} supplierId={supplierId} product={termsProduct} open={Boolean(termsProduct)} onOpenChange={(open) => { if (!open) setTermsProduct(null) }} />
  </>
}

function PurchaseHistory({ data }: { data: SupplierDetailData['purchase_history'] }) {
  return <section className="supplier-activity panel" aria-labelledby="supplier-activity-title">
    <div className="supplier-section-heading"><div><h2 id="supplier-activity-title">Purchase and receipt history</h2><p>Recent activity visible to your Odoo role.</p></div><Clock3 size={17} aria-hidden="true" /></div>
    {!data.available ? <p className="supplier-history-note"><CircleHelp size={15} aria-hidden="true" />{data.note}</p> : data.items.length ? <ol className="supplier-activity-list">{data.items.map((item) => <li key={`${item.kind}-${item.id}`}><span className={`supplier-activity-icon is-${item.kind}`}><Truck size={15} aria-hidden="true" /></span><span><strong>{item.label}</strong><small>{item.reference || 'No reference recorded'}</small></span><time>{item.date ? new Date(item.date.replace(' ', 'T') + (item.date.endsWith('Z') ? '' : 'Z')).toLocaleDateString() : 'Date not recorded'}</time></li>)}</ol> : <p className="supplier-history-note">No recent purchase orders or incoming receipts are visible for this supplier.</p>}
  </section>
}

function SupplierDetail({ supplierId, companyId, session, onSwitchCompany, onSignOut }: WorkspaceSessionValue & { supplierId: number }) {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<PartStatus>('all')
  const [page, setPage] = useState(1)
  const [selectedProduct, setSelectedProduct] = useState<ProductStub | null>(null)
  const detail = useQuery({ queryKey: ['supplier-detail', companyId, supplierId], queryFn: () => api.supplierDetail(companyId, supplierId) })
  const supplier = detail.data?.supplier
  const summary = detail.data?.summary
  const company = session.allowed_companies.find((item) => item.id === companyId) ?? session.current_company

  return <SupplierWorkspace workspace={{ session, companyId, onSwitchCompany, onSignOut }} activeSection="suppliers" selectedProduct={selectedProduct} onSelectProduct={setSelectedProduct}>
    <main className="page-content inventory-page supplier-page supplier-detail-page">
      <Link className="warehouse-back-link" to="/suppliers"><ChevronLeft size={15} aria-hidden="true" />All suppliers</Link>
      {detail.isError && !detail.data ? <SupplierError error={detail.error} detail onRetry={() => void detail.refetch()} /> : detail.isPending && !detail.data ? <SupplierLoading detail /> : supplier && summary ? <>
        <div className="page-heading inventory-page-heading supplier-page-heading supplier-detail-heading">
          <div><div className="inventory-eyebrow"><Building2 size={14} aria-hidden="true" /> Supplier details</div><h1>{supplier.name}</h1><p>{supplier.vendor_code ? `Vendor code ${supplier.vendor_code} · ` : ''}Supplier relationship for {company.name}.</p><ContactDetails supplier={supplier} /></div>
          <span className="warehouse-readonly-mark"><ShieldCheck size={14} aria-hidden="true" /> Read-only view</span>
        </div>
        <div className="inventory-summary-grid supplier-detail-metrics" aria-label="Supplier summary">
          <article className="inventory-summary-card tone-violet"><span className="inventory-summary-icon"><PackageSearch size={17} /></span><div className="inventory-summary-copy"><span>Parts supplied</span><strong>{count(summary.active_parts)}</strong><small>With current supplier terms</small></div></article>
          <article className="inventory-summary-card tone-green"><span className="inventory-summary-icon"><Check size={17} /></span><div className="inventory-summary-copy"><span>Tracked parts</span><strong>{count(summary.tracked_parts)}</strong><small>Included in stock monitoring</small></div></article>
          <article className="inventory-summary-card tone-amber"><span className="inventory-summary-icon"><Truck size={17} /></span><div className="inventory-summary-copy"><span>Parts to restock</span><strong>{count(summary.reorder_parts)}</strong><small>Parts in current suggestions</small></div></article>
          <article className="inventory-summary-card tone-red"><span className="inventory-summary-icon"><Clock3 size={17} /></span><div className="inventory-summary-copy"><span>Lead-time range</span><strong>{leadRangeText(summary)}</strong><small>Across current supplier terms</small></div></article>
        </div>
        {!detail.data.coverage.reorder_complete && <p className="inventory-summary-caveat" role="note"><CircleHelp size={14} aria-hidden="true" />Restock links are incomplete because the company stock scan reached its safe review limit.</p>}
        <SupplierPartTable key={`${supplierId}-${companyId}`} companyId={companyId} supplierId={supplierId} query={query} setQuery={setQuery} status={status} setStatus={setStatus} page={page} setPage={setPage} onSelectProduct={setSelectedProduct} />
        <PurchaseHistory data={detail.data.purchase_history} />
      </> : null}
    </main>
  </SupplierWorkspace>
}

function MissingSupplierParts({ companyId, session, onSwitchCompany, onSignOut }: WorkspaceSessionValue) {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<PartStatus>('all')
  const [page, setPage] = useState(1)
  const [selectedProduct, setSelectedProduct] = useState<ProductStub | null>(null)
  const debouncedQuery = useDebounce(query.trim(), 250)
  const request: SupplierPartsRequest = { query: debouncedQuery, status, sort: 'name', direction: 'asc', page, pageSize: PART_PAGE_SIZE }
  const parts = useQuery({ queryKey: ['supplier-gaps', companyId, request], queryFn: () => api.supplierGaps(companyId, request), placeholderData: keepPreviousData })
  const company = session.allowed_companies.find((item) => item.id === companyId) ?? session.current_company

  function stub(item: SupplierPart): ProductStub { return { id: item.product_id, name: item.name, sku: item.sku, reference: item.reference, category: item.category } }

  return <SupplierWorkspace workspace={{ session, companyId, onSwitchCompany, onSignOut }} activeSection="suppliers" selectedProduct={selectedProduct} onSelectProduct={setSelectedProduct}>
    <main className="page-content inventory-page supplier-page supplier-missing-page">
      <Link className="warehouse-back-link" to="/suppliers"><ChevronLeft size={15} aria-hidden="true" />All suppliers</Link>
      <div className="page-heading inventory-page-heading supplier-page-heading"><div><div className="inventory-eyebrow"><PackageSearch size={14} aria-hidden="true" /> Supplier coverage</div><h1>Parts without a supplier</h1><p>Find active parts with no supplier terms configured for {company.name}. Stock and any current restock suggestions come from Odoo.</p></div><span className="warehouse-readonly-mark"><ShieldCheck size={14} aria-hidden="true" /> Read-only view</span></div>
      {parts.isError && !parts.data ? <SupplierError error={parts.error} onRetry={() => void parts.refetch()} /> : parts.isPending && !parts.data ? <SupplierLoading /> : parts.data ? <>
        <div className="supplier-gap-banner"><span><AlertCircle size={18} aria-hidden="true" /></span><div><strong>{count(parts.data.pagination.total_count)} parts match</strong><p>These active parts have no configured supplier term. This view does not estimate a supplier or purchase price.</p></div></div>
        <section className="supplier-parts-panel panel" aria-labelledby="missing-parts-title">
          <div className="supplier-section-heading"><div><h2 id="missing-parts-title">Parts to review</h2><p>Search by part name, SKU, or OEM reference. Filter results by current stock status.</p></div><span className="inventory-live-mark"><i aria-hidden="true" /> Current stock</span></div>
          <div className="supplier-filter-area supplier-parts-filter-area">
            <label className="inventory-search-field"><Search size={16} aria-hidden="true" /><span className="sr-only">Search parts without a supplier</span><input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1) }} placeholder="Search parts, SKU, or OEM reference…" type="search" autoComplete="off" />{query && <button type="button" aria-label="Clear part search" onClick={() => { setQuery(''); setPage(1) }}>Clear</button>}</label>
            <label className="inventory-select-wrap"><span>Stock status</span><select aria-label="Filter parts without a supplier by stock status" value={status} onChange={(event) => { setStatus(event.target.value as PartStatus); setPage(1) }}><option value="all">All parts</option><option value="in_stock">In stock</option><option value="low_stock">Low stock</option><option value="out_of_stock">Out of stock</option></select></label>
          </div>
          {parts.data.items.length ? <>
            <div className="supplier-part-table-wrap"><table className="supplier-part-table supplier-gaps-table"><thead><tr><th>Part</th><th>Stock status</th><th>On hand</th><th>Available to use</th><th>Suggested order</th><th>Supplier terms</th><th><span className="sr-only">Part details</span></th></tr></thead><tbody>{parts.data.items.map((item) => <tr key={item.product_id}><td><button className="supplier-part-name" type="button" onClick={() => setSelectedProduct(stub(item))}><strong>{item.name}</strong><small>{item.sku}{item.reference ? ` · ${item.reference}` : ''}</small></button></td><td><StockStatus status={item.status} /></td><td>{quantity(item.on_hand, item.uom)}</td><td>{quantity(item.available, item.uom)}</td><td><ReorderContext item={item} /></td><td><span className="supplier-missing-pill">No supplier on file</span></td><td><button className="supplier-open-link" type="button" onClick={() => setSelectedProduct(stub(item))}>View part <ChevronRight size={14} /></button></td></tr>)}</tbody></table></div>
            <div className="supplier-part-mobile-list">{parts.data.items.map((item) => <article className="supplier-part-card" key={item.product_id}><div className="supplier-part-card-heading"><button className="supplier-part-name" type="button" onClick={() => setSelectedProduct(stub(item))}><strong>{item.name}</strong><small>{item.sku}{item.reference ? ` · ${item.reference}` : ''}</small></button><StockStatus status={item.status} /></div><div className="supplier-part-card-values"><span><small>On hand</small><strong>{quantity(item.on_hand, item.uom)}</strong></span><span><small>Available to use</small><strong>{quantity(item.available, item.uom)}</strong></span></div><div className="supplier-part-card-foot"><ReorderContext item={item} /><span className="supplier-missing-pill">No supplier on file</span></div></article>)}</div>
            {!parts.data.coverage.reorder_complete && <p className="inventory-summary-caveat supplier-parts-caveat" role="note"><CircleHelp size={14} aria-hidden="true" />Restock suggestions are incomplete because the company stock scan reached its safe review limit.</p>}
            <SupplierPagination page={parts.data.pagination.page} pageSize={parts.data.pagination.page_size} totalPages={parts.data.pagination.total_pages} totalCount={parts.data.pagination.total_count} hasPrevious={parts.data.pagination.has_previous} hasNext={parts.data.pagination.has_next} onPage={setPage} />
          </> : <section className="supplier-empty"><span className="inventory-state-icon"><Check size={22} aria-hidden="true" /></span><h2>{query || status !== 'all' ? 'No parts match these filters' : 'Every active part has a supplier term'}</h2><p>{query || status !== 'all' ? 'Try another search or stock status.' : 'There are no active storable parts without supplier terms in this company.'}</p>{(query || status !== 'all') && <button className="inventory-secondary-button" type="button" onClick={() => { setQuery(''); setStatus('all'); setPage(1) }}>Clear filters</button>}</section>}
          {parts.isFetching && <div className="warehouse-fetching" role="status">Updating parts…</div>}
        </section>
      </> : null}
    </main>
  </SupplierWorkspace>
}

function SupplierWorkspace({ workspace, activeSection, selectedProduct, onSelectProduct, children }: {
  workspace: WorkspaceSessionValue; activeSection: DashboardSection; selectedProduct: ProductStub | null; onSelectProduct: (product: ProductStub | null) => void; children: ReactNode
}) {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const navigate = useNavigate()
  const { session, companyId, onSwitchCompany, onSignOut } = workspace

  useEffect(() => {
    function onShortcut(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); setSearchOpen((open) => !open) }
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

  return <>
    <DashboardShell collapsed={collapsed} onToggleCollapsed={() => setCollapsed((value) => !value)} activeSection={activeSection} onNavigate={navigateTo} onUnavailable={() => undefined} onOpenSearch={() => setSearchOpen(true)} mobileNavOpen={mobileNavOpen} onMobileNavChange={setMobileNavOpen} session={session} companyId={companyId} onSwitchCompany={onSwitchCompany} onSignOut={onSignOut}>{children}</DashboardShell>
    <ProductSearchDialog companyId={companyId} open={searchOpen} onOpenChange={setSearchOpen} onSelectProduct={(product) => { onSelectProduct({ id: product.id, name: product.name, sku: product.sku, reference: product.reference, category: product.category }); setSearchOpen(false) }} />
    {selectedProduct && <InventoryDetailSheet product={{ product_id: selectedProduct.id, name: selectedProduct.name, sku: selectedProduct.sku, reference: selectedProduct.reference, category: selectedProduct.category }} companyId={companyId} locale={session.user.locale} timezone={session.user.timezone} onClose={() => onSelectProduct(null)} />}
  </>
}

export function SuppliersPage() {
  return <WorkspaceSession>{(value) => <SupplierOverview {...value} />}</WorkspaceSession>
}

export function SupplierDetailPage({ supplierId }: { supplierId: number }) {
  return <WorkspaceSession>{(value) => <SupplierDetail {...value} supplierId={supplierId} />}</WorkspaceSession>
}

export function SupplierGapsPage() {
  return <WorkspaceSession>{(value) => <MissingSupplierParts {...value} />}</WorkspaceSession>
}
