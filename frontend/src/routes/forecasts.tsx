import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useSearch } from '@tanstack/react-router'
import {
  AlertCircle, Boxes, CalendarDays, ChartNoAxesCombined,
  ChevronLeft, ChevronRight, CircleHelp, Clock3, Database, History,
  PackageSearch, Search, ShieldCheck, SlidersHorizontal, Sparkles,
  Warehouse as WarehouseIcon,
} from 'lucide-react'
import {
  Area, CartesianGrid, ComposedChart, Line, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { ApiError, api, type ForecastsRequest } from '@/api/client'
import type { ForecastDetailData, ForecastEstimate, ForecastListRun, ForecastPart, ForecastPartHorizon, ForecastsData } from '@/api/contracts'
import { DashboardShell, type DashboardSection } from '@/components/gate-one/dashboard-shell'
import { InventoryDetailSheet } from '@/components/inventory/inventory-detail-sheet'
import { ProductSearchDialog, type ProductSearchItem } from '@/components/gate-two/product-search-dialog'
import { WorkspaceSession, type WorkspaceSessionValue } from '@/components/workspace-session'
import { useDebounce } from '@/hooks/use-debounce'
import { formatQuantity } from '@/lib/dashboard'
import { buildForecastChartPoints, formatEmployeeForecastTotal, formatForecastDate, formatForecastDateTime, formatForecastTime, type ForecastChartPoint } from '@/lib/forecasts'
import '@/styles/inventory.css'
import '@/styles/forecasts.css'

const PART_PAGE_SIZE = 12
const HISTORY_PAGE_SIZE = 25
type ProductStub = Pick<ProductSearchItem, 'id' | 'name' | 'sku' | 'reference' | 'category'>
type RunState = ForecastsRequest['state']
type ReviewFilter = NonNullable<ForecastsRequest['reviewStatus']>
type SourceFilter = NonNullable<ForecastsRequest['sourceType']>
type HorizonFilter = NonNullable<ForecastsRequest['horizonDays']>

function count(value: number) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value)
}

function statusLabel(state: ForecastListRun['state']) {
  const labels: Record<ForecastListRun['state'], string> = {
    queued: 'Waiting to run',
    running: 'Calculating',
    completed: 'Calculated',
    insufficient_history: 'Not enough history',
    no_observed_demand: 'No deliveries recorded',
    failed: 'Could not calculate',
  }
  return labels[state]
}

function stateTone(state: ForecastListRun['state']) {
  if (state === 'completed') return 'is-complete'
  if (state === 'queued' || state === 'running') return 'is-pending'
  return 'is-warning'
}

function reviewLabel(status: ForecastListRun['review_status']) {
  return status === 'reviewed' ? 'Reviewed' : 'Needs review'
}

function methodLabel(value: string | false) {
  if (!value) return 'Not available'
  const labels: Record<string, string> = {
    random_forest: 'Random forest model',
    ml_random_forest: 'Random forest model',
    trailing_mean: 'Recent average',
    seasonal_naive: 'Recent seasonal pattern',
    croston_sba: 'Intermittent-sales baseline',
  }
  return labels[value] ?? value.replaceAll('_', ' ')
}

function ForecastState({ title, children, icon: Icon = PackageSearch }: {
  title: string; children: ReactNode; icon?: typeof PackageSearch
}) {
  return <section className="forecast-state panel"><span className="forecast-state-icon"><Icon size={22} aria-hidden="true" /></span><h2>{title}</h2><p>{children}</p></section>
}

function ForecastError({ error, onRetry }: { error: Error; onRetry: () => void }) {
  const forbidden = error instanceof ApiError && error.code === 'forbidden'
  return <ForecastState title={forbidden ? 'Forecasts are restricted' : 'Forecasts could not be loaded'} icon={AlertCircle}>
    {forbidden ? 'Your current role cannot view forecast data for this company. Ask your administrator to review your access.' : error.message}
    {!forbidden && <button className="inventory-secondary-button" type="button" onClick={onRetry}>Try again</button>}
  </ForecastState>
}

function ForecastLoading({ detail = false }: { detail?: boolean }) {
  return <section className="forecast-loading panel" role="status" aria-label={detail ? 'Loading forecast details' : 'Loading saved forecasts'}><span className="sr-only">Loading forecast records from Odoo…</span><i /><i /><i /><i /></section>
}

function ForecastPill({ run }: { run: ForecastListRun }) {
  return <span className={`forecast-status ${stateTone(run.state)}`}><i aria-hidden="true" />{statusLabel(run.state)}</span>
}

function SourcePill({ sourceType }: { sourceType: ForecastListRun['source_type'] }) {
  return sourceType === 'synthetic_demo'
    ? <span className="forecast-source is-demo"><Sparkles size={12} aria-hidden="true" />Synthetic showroom</span>
    : <span className="forecast-source"><Database size={12} aria-hidden="true" />Completed deliveries</span>
}

function ForecastMobileCard({ run, timezone, view }: { run: ForecastListRun; timezone: string; view: 'parts' | 'history' }) {
  return <Link className="forecast-mobile-card" to="/forecasts/$runId" params={{ runId: String(run.id) }} search={{ view }} aria-label={`Open forecast for ${run.product_name}, SKU ${run.sku}`}>
    <div className="forecast-mobile-card-top"><span className="forecast-mobile-part"><strong>{run.product_name}</strong><small>SKU {run.sku}</small></span><ChevronRight size={17} aria-hidden="true" /></div>
    <div className="forecast-mobile-badges"><ForecastPill run={run} /><span className={`forecast-review ${run.review_status === 'reviewed' ? 'is-reviewed' : 'is-unreviewed'}`}>{reviewLabel(run.review_status)}</span></div>
    <div className="forecast-mobile-details"><span><WarehouseIcon size={13} aria-hidden="true" />{run.warehouse_name || 'Company-wide'}</span><span><CalendarDays size={13} aria-hidden="true" />{run.horizon_days} days</span></div>
    <div className="forecast-mobile-foot"><SourcePill sourceType={run.source_type} /><span>Saved <span data-testid="forecast-saved-date">{formatForecastDate(run.created_at, timezone)}</span></span></div>
  </Link>
}

function ForecastPagination({ data, onPage }: { data: ForecastsData; onPage: (page: number) => void }) {
  const pagination = data.pagination
  const first = pagination.total_count ? (pagination.page - 1) * pagination.page_size + 1 : 0
  const last = Math.min(pagination.page * pagination.page_size, pagination.total_count)
  return <div className="forecast-pagination"><span>Showing {count(first)}–{count(last)} of {count(pagination.total_count)} forecasts</span><div><button type="button" aria-label="Previous page" disabled={!pagination.has_previous} onClick={() => onPage(pagination.page - 1)}><ChevronLeft size={16} /></button><span>Page {pagination.page} of {Math.max(1, pagination.total_pages)}</span><button type="button" aria-label="Next page" disabled={!pagination.has_next} onClick={() => onPage(pagination.page + 1)}><ChevronRight size={16} /></button></div></div>
}

function PartPagination({ page, hasPrevious, hasNext, onPage }: {
  page: number; hasPrevious: boolean; hasNext: boolean; onPage: (page: number) => void
}) {
  return <div className="forecast-pagination" aria-label="Part results pages"><span>Part results · page {page}</span><div><button type="button" aria-label="Previous part results page" disabled={!hasPrevious} onClick={() => onPage(page - 1)}><ChevronLeft size={16} /></button><span>Page {page}</span><button type="button" aria-label="Next part results page" disabled={!hasNext} onClick={() => onPage(page + 1)}><ChevronRight size={16} /></button></div></div>
}

function partEstimateMessage(entry: ForecastPartHorizon) {
  if (!entry.latest_run) return `No ${entry.horizon_days}-day estimate is saved for this part and warehouse.`
  if (entry.estimate.status === 'available') return ''
  const messages: Record<ForecastListRun['state'], string> = {
    queued: 'This estimate is waiting to be prepared.',
    running: 'This estimate is still being prepared.',
    completed: 'A complete daily estimate is not available, so a total cannot be shown.',
    insufficient_history: 'There is not enough recorded delivery history for this estimate.',
    no_observed_demand: 'No completed deliveries were recorded in the selected history period.',
    failed: 'This estimate could not be calculated.',
  }
  return messages[entry.latest_run.state]
}

function ForecastPartRow({ part, view, timezone, onShowHistory }: {
  part: ForecastPart
  view: 'parts' | 'history'
  timezone: string
  onShowHistory: (part: ForecastPart) => void
}) {
  const [selectedHorizon, setSelectedHorizon] = useState<7 | 30 | 60>(30)
  const selected = part.horizons.find((item) => item.horizon_days === selectedHorizon) ?? part.horizons[1]
  const run = selected.latest_run
  const estimate = selected.estimate
  const dateRange = estimate.status === 'available' && estimate.date_start && estimate.date_end
    ? `${formatForecastDate(estimate.date_start, timezone, { year: 'numeric' })} – ${formatForecastDate(estimate.date_end, timezone, { year: 'numeric' })}`
    : false

  return <article className="forecast-part-row" data-product-id={part.product_id} data-warehouse-id={part.warehouse_id || 'company'}>
    <div className="forecast-part-identity">
      <span className="forecast-row-icon"><Boxes size={16} aria-hidden="true" /></span>
      <div><strong>{part.product_name}</strong><small>SKU {part.sku}</small><span className="forecast-part-warehouse"><WarehouseIcon size={13} aria-hidden="true" />{part.warehouse_name || 'Company-wide'}</span></div>
    </div>
    <div className="forecast-part-period">
      <span className="forecast-part-field-label">Forecast period</span>
      <div className="forecast-horizon-control" role="group" aria-label={`${part.product_name} forecast period`}>
        {([7, 30, 60] as const).map((horizon) => <button key={horizon} type="button" aria-pressed={selectedHorizon === horizon} onClick={() => setSelectedHorizon(horizon)}>{horizon} days</button>)}
      </div>
      {selected.saved_run_count > 0 && <small className="forecast-run-count">{count(selected.saved_run_count)} saved run{selected.saved_run_count === 1 ? '' : 's'} for this period</small>}
    </div>
    <div className="forecast-part-estimate" aria-live="polite">
      {run && <div className="forecast-part-statuses"><ForecastPill run={run as ForecastListRun} /><span className={`forecast-review ${run.review_status === 'reviewed' ? 'is-reviewed' : 'is-unreviewed'}`}>{reviewLabel(run.review_status)}</span></div>}
      {estimate.status === 'available' && run && estimate.estimated_units !== false && estimate.uom_rounding !== false && estimate.uom ? <>
        <span className="forecast-part-field-label">Estimated deliveries</span>
        <strong className="forecast-estimate-total" data-testid="forecast-estimated-total">{formatEmployeeForecastTotal(estimate.estimated_units, estimate.uom_rounding, estimate.uom)}</strong>
        <span className="forecast-estimate-range" data-testid="forecast-estimate-range">{dateRange}</span>
        {estimate.window_status === 'ended' && <small className="forecast-window-note">This saved estimate period has ended.</small>}
        {estimate.window_status === 'in_progress' && <small className="forecast-window-note">This saved estimate period is in progress.</small>}
      </> : <p className="forecast-part-empty-copy">{partEstimateMessage(selected)}</p>}
      <div className="forecast-part-actions">
        {run ? <Link className="forecast-open-estimate" to="/forecasts/$runId" params={{ runId: String(run.id) }} search={{ view }} aria-label={`Open ${selectedHorizon}-day estimate for ${part.product_name}, SKU ${part.sku}`}>
          {estimate.status === 'available' ? 'View estimate' : 'View details'}<ChevronRight size={16} aria-hidden="true" />
        </Link> : <button className="forecast-open-estimate" type="button" onClick={() => onShowHistory(part)}>View saved history<ChevronRight size={16} aria-hidden="true" /></button>}
      </div>
    </div>
  </article>
}

function ForecastOverview({ companyId, session, onSwitchCompany, onSignOut }: WorkspaceSessionValue) {
  const search = useSearch({ from: '/forecasts' })
  const view = search.view ?? 'parts'
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [warehouseId, setWarehouseId] = useState<number | undefined>()
  const [horizonDays, setHorizonDays] = useState<HorizonFilter>('all')
  const [state, setState] = useState<RunState>('all')
  const [reviewStatus, setReviewStatus] = useState<ReviewFilter>('all')
  const [sourceType, setSourceType] = useState<SourceFilter>('all')
  const [partsPage, setPartsPage] = useState(1)
  const [historyPage, setHistoryPage] = useState(1)
  const [selectedProduct, setSelectedProduct] = useState<ProductStub | null>(null)
  const debouncedQuery = useDebounce(query.trim(), 250)
  const partFilters = { query: debouncedQuery, warehouseId, page: partsPage, pageSize: PART_PAGE_SIZE }
  const historyFilters: ForecastsRequest = { query: debouncedQuery, warehouseId, horizonDays, state, reviewStatus, sourceType, page: historyPage, pageSize: HISTORY_PAGE_SIZE }
  const parts = useQuery({ queryKey: ['forecast-parts', companyId, partFilters], queryFn: () => api.forecastParts(companyId, partFilters), placeholderData: keepPreviousData, enabled: view === 'parts' })
  const forecasts = useQuery({ queryKey: ['forecasts', companyId, historyFilters], queryFn: () => api.forecasts(companyId, historyFilters), placeholderData: keepPreviousData, enabled: view === 'history' })
  const company = session.allowed_companies.find((item) => item.id === companyId) ?? session.current_company
  const historyFilterActive = Boolean(horizonDays !== 'all' || state !== 'all' || reviewStatus !== 'all' || sourceType !== 'all')
  const warehouseOptions = view === 'parts' ? parts.data?.warehouse_options : forecasts.data?.warehouse_options
  const warehouseOptionsLimited = view === 'parts' ? parts.data?.warehouse_options_limited : forecasts.data?.warehouse_options_limited
  const warehouseCount = view === 'parts' ? parts.data?.warehouse_count : forecasts.data?.warehouse_count

  function changeView(next: 'parts' | 'history') {
    void navigate({ to: '/forecasts', search: { view: next }, replace: true })
  }

  function clearHistoryFilters() {
    setHorizonDays('all'); setState('all'); setReviewStatus('all'); setSourceType('all'); setHistoryPage(1)
  }

  function showSavedHistory(part?: ForecastPart) {
    if (part) {
      setQuery(part.sku)
      setWarehouseId(part.warehouse_id || undefined)
    }
    clearHistoryFilters()
    setPartsPage(1)
    changeView('history')
  }

  return <ForecastWorkspace workspace={{ session, companyId, onSwitchCompany, onSignOut }} activeSection="forecast" selectedProduct={selectedProduct} onSelectProduct={setSelectedProduct}>
    <main className="page-content inventory-page forecasts-page">
      <div className="page-heading inventory-page-heading forecasts-page-heading">
        <div><div className="inventory-eyebrow"><ChartNoAxesCombined size={14} aria-hidden="true" /> Stock planning</div><h1>Forecasts</h1><p>See completed deliveries and saved estimates for parts at {company.name}.</p></div>
        <span className="warehouse-readonly-mark"><ShieldCheck size={14} aria-hidden="true" /> View only</span>
      </div>
      <nav className="forecast-view-tabs" aria-label="Forecast views">
        <button type="button" aria-pressed={view === 'parts'} className={view === 'parts' ? 'is-active' : ''} onClick={() => changeView('parts')}>By part</button>
        <button type="button" aria-pressed={view === 'history'} className={view === 'history' ? 'is-active' : ''} onClick={() => changeView('history')}><History size={15} aria-hidden="true" />Saved run history</button>
      </nav>
      <section className="forecast-catalog panel" aria-labelledby="forecast-list-title">
        <div className="forecast-catalog-heading"><div className="inventory-catalog-title"><span className="inventory-catalog-icon"><ChartNoAxesCombined size={18} aria-hidden="true" /></span><div><h2 id="forecast-list-title">{view === 'parts' ? 'Forecasts by part' : 'Saved run history'}</h2><p>{view === 'parts' ? 'Choose a part and period to see its latest saved estimate.' : 'Every saved run remains available here, including older and incomplete estimates.'}</p></div></div><span className="inventory-live-mark"><i aria-hidden="true" /> Live Odoo data</span></div>
        <div className="forecast-filter-area">
          <label className="inventory-search-field"><Search size={16} aria-hidden="true" /><span className="sr-only">{view === 'parts' ? 'Search forecast parts by name or SKU' : 'Search saved forecasts by part name or SKU'}</span><input value={query} onChange={(event) => { setQuery(event.target.value); setPartsPage(1); setHistoryPage(1) }} placeholder="Search part name or SKU…" type="search" autoComplete="off" />{query && <button type="button" aria-label="Clear forecast search" onClick={() => { setQuery(''); setPartsPage(1); setHistoryPage(1) }}>Clear</button>}</label>
          <label className="inventory-select-wrap forecast-warehouse-control"><span>Warehouse</span><select aria-label="Choose forecast warehouse" aria-describedby="forecast-warehouse-help" value={warehouseId ?? ''} onChange={(event) => { setWarehouseId(event.target.value ? Number(event.target.value) : undefined); setPartsPage(1); setHistoryPage(1) }}><option value="">All locations</option>{warehouseOptions?.map((warehouse) => <option key={warehouse.id} value={warehouse.id}>{warehouse.name}</option>)}</select><span id="forecast-warehouse-help" className="sr-only">Includes warehouse-specific and company-wide forecasts.</span></label>
          {view === 'history' && <details className="forecast-advanced-filters"><summary><SlidersHorizontal size={15} aria-hidden="true" />More filters</summary><div className="forecast-advanced-grid">
            <label className="inventory-select-wrap"><span>Forecast period</span><select aria-label="Filter forecasts by horizon" value={horizonDays} onChange={(event) => { setHorizonDays(event.target.value === 'all' ? 'all' : Number(event.target.value) as 7 | 30 | 60); setHistoryPage(1) }}><option value="all">All periods</option><option value="7">7 days</option><option value="30">30 days</option><option value="60">60 days</option></select></label>
            <label className="inventory-select-wrap"><span>Estimate status</span><select aria-label="Filter forecasts by run status" value={state} onChange={(event) => { setState(event.target.value as RunState); setHistoryPage(1) }}><option value="all">All statuses</option><option value="queued">Waiting to run</option><option value="running">Calculating</option><option value="completed">Calculated</option><option value="insufficient_history">Not enough history</option><option value="no_observed_demand">No deliveries recorded</option><option value="failed">Could not calculate</option></select></label>
            <label className="inventory-select-wrap"><span>Review</span><select aria-label="Filter forecasts by review status" value={reviewStatus} onChange={(event) => { setReviewStatus(event.target.value as ReviewFilter); setHistoryPage(1) }}><option value="all">All review states</option><option value="reviewed">Reviewed</option><option value="unreviewed">Needs review</option></select></label>
            <label className="inventory-select-wrap"><span>Source</span><select aria-label="Filter forecasts by source" value={sourceType} onChange={(event) => { setSourceType(event.target.value as SourceFilter); setHistoryPage(1) }}><option value="all">All sources</option><option value="completed_deliveries">Completed deliveries</option><option value="synthetic_demo">Synthetic demo examples</option></select></label>
            {historyFilterActive && <button className="forecast-clear-filters" type="button" onClick={clearHistoryFilters}>Clear filters</button>}
          </div></details>}
        </div>
        {warehouseOptionsLimited && warehouseCount !== undefined && <p className="forecast-filter-note" role="note">Choose from the first 100 warehouses shown. Search and saved-run history continue to use your full permitted company scope.</p>}
        {view === 'parts' ? <>
          {parts.isError && !parts.data ? <ForecastError error={parts.error} onRetry={() => void parts.refetch()} /> : parts.isPending && !parts.data ? <ForecastLoading /> : parts.data ? <>
            {parts.data.access_note && <p className="forecast-access-note" role="note"><CircleHelp size={15} aria-hidden="true" />{parts.data.access_note}<button type="button" className="forecast-inline-link" onClick={() => showSavedHistory()}>Open saved run history</button></p>}
            {parts.data.parts.length ? <>
              <div className="forecast-part-list" aria-label="Parts with saved delivery forecasts">{parts.data.parts.map((part) => <ForecastPartRow key={`${part.product_id}-${part.warehouse_id || 'company'}`} part={part} view={view} timezone={session.user.timezone} onShowHistory={showSavedHistory} />)}</div>
              <PartPagination page={parts.data.pagination.page} hasPrevious={parts.data.pagination.has_previous} hasNext={parts.data.pagination.has_next} onPage={setPartsPage} />
            </> : <div className="forecast-empty"><span className="inventory-state-icon"><PackageSearch size={22} aria-hidden="true" /></span><h2>{debouncedQuery || warehouseId ? 'No parts match your search' : 'No saved delivery estimates yet'}</h2><p>{debouncedQuery || warehouseId ? 'Try another part name, SKU, or warehouse.' : parts.data.real_history_access ? 'When saved forecasts are available for your company, each part will appear here once per warehouse.' : 'Synthetic examples are kept separate from real delivery forecasts and remain available in Saved run history.'}</p>{!parts.data.real_history_access && <button type="button" className="inventory-secondary-button" onClick={() => showSavedHistory()}>Open saved run history</button>}</div>}
            {parts.isFetching && <div className="forecast-fetching" role="status">Updating part results…</div>}
          </> : null}
        </> : <>
          {forecasts.isError && !forecasts.data ? <ForecastError error={forecasts.error} onRetry={() => void forecasts.refetch()} /> : forecasts.isPending && !forecasts.data ? <ForecastLoading /> : forecasts.data ? <>
            {forecasts.data.access_note && <p className="forecast-access-note" role="note"><CircleHelp size={15} aria-hidden="true" />{forecasts.data.access_note}</p>}
            <p className="forecast-history-count">{forecasts.data.pagination.total_count === 1 ? '1 saved run matches your filters.' : `${count(forecasts.data.pagination.total_count)} saved runs match your filters.`} Each row opens the exact saved estimate.</p>
            {forecasts.data.runs.length ? <>
              <div className="forecast-table-wrap"><table className="forecast-table"><thead><tr><th>Part</th><th>Warehouse / source</th><th>Period / recorded history</th><th>Estimate status</th><th>Review</th><th>Saved</th><th><span className="sr-only">Details</span></th></tr></thead><tbody>{forecasts.data.runs.map((run) => <tr key={run.id}><td><ForecastRowPart run={run} view={view} /></td><td><span className="forecast-table-scope">{run.warehouse_name || 'Company-wide'}</span><small className="forecast-table-source">{run.source_type === 'synthetic_demo' ? 'Synthetic demo example' : 'Completed deliveries'}</small></td><td><strong>{run.horizon_days} days</strong><small>{formatForecastDate(run.history_start, session.user.timezone)} – {formatForecastDate(run.history_end, session.user.timezone)}</small></td><td><ForecastPill run={run} /></td><td><span className={`forecast-review ${run.review_status === 'reviewed' ? 'is-reviewed' : 'is-unreviewed'}`}>{reviewLabel(run.review_status)}</span></td><td><strong data-testid="forecast-saved-date">{formatForecastDate(run.created_at, session.user.timezone, { year: 'numeric' })}</strong><small data-testid="forecast-saved-time">{formatForecastTime(run.created_at, session.user.timezone)}</small></td><td><Link className="forecast-table-open" to="/forecasts/$runId" params={{ runId: String(run.id) }} search={{ view }} aria-label={`Open forecast for ${run.product_name}, SKU ${run.sku}`}><ChevronRight size={17} aria-hidden="true" /></Link></td></tr>)}</tbody></table></div>
              <div className="forecast-mobile-list">{forecasts.data.runs.map((run) => <ForecastMobileCard key={run.id} run={run} timezone={session.user.timezone} view={view} />)}</div>
              <ForecastPagination data={forecasts.data} onPage={setHistoryPage} />
            </> : <div className="forecast-empty"><span className="inventory-state-icon"><PackageSearch size={22} aria-hidden="true" /></span><h2>{query || warehouseId || historyFilterActive ? 'No saved runs match these filters' : 'No saved forecast runs yet'}</h2><p>{query || warehouseId || historyFilterActive ? 'Try a different part, warehouse, period, status, review state, or source. Clear filters to see all saved runs available to your role.' : 'Saved runs, including incomplete and demo examples, will appear here when available to your role.'}</p>{(query || warehouseId || historyFilterActive) && <button className="inventory-secondary-button" type="button" onClick={() => { setQuery(''); setWarehouseId(undefined); clearHistoryFilters(); setHistoryPage(1) }}>Clear filters</button>}</div>}
            {forecasts.isFetching && <div className="forecast-fetching" role="status">Updating saved runs…</div>}
          </> : null}
        </>}
      </section>
    </main>
  </ForecastWorkspace>
}

function ForecastRowPart({ run, view }: { run: ForecastListRun; view: 'parts' | 'history' }) {
  return <Link className="forecast-table-part" to="/forecasts/$runId" params={{ runId: String(run.id) }} search={{ view }}><span className="forecast-row-icon"><Boxes size={16} aria-hidden="true" /></span><span><strong>{run.product_name}</strong><small>SKU {run.sku}</small></span></Link>
}

function ForecastTooltip({ active, payload, label, uom }: {
  active?: boolean
  payload?: ReadonlyArray<{ payload: ForecastChartPoint; dataKey?: string }>
  label?: string | number
  uom: string
}) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload
  return <div className="forecast-tooltip"><strong>{String(label)}</strong>{point.future ? <>
    <span className="forecast-tooltip-key is-forecast">Estimated deliveries <b>{point.forecast === null ? '—' : `${formatQuantity(point.forecast)} ${uom}`}</b></span>
    {point.lower !== null && point.band !== null && <small>Planning range {formatQuantity(point.lower)}–{formatQuantity(point.lower + point.band)} {uom}; not a guarantee</small>}
  </> : <>
    <span className="forecast-tooltip-key is-history">Completed deliveries <b>{point.actual === null ? '—' : `${formatQuantity(point.actual)} ${uom}`}</b></span>
    {(point.returns ?? 0) > 0 && <small>Completed returns recorded separately: {formatQuantity(point.returns ?? 0)} {uom}</small>}
    {(point.events ?? 0) > 0 && <small>{count(point.events ?? 0)} completed stock event{point.events === 1 ? '' : 's'}</small>}
  </>}</div>
}

function ForecastChart({ run, timezone }: { run: ForecastDetailData['run']; timezone: string }) {
  const data = useMemo(() => buildForecastChartPoints(run), [run])
  const firstFutureDate = run.predictions[0]?.day
  const firstPrediction = run.predictions[0]
  const formatter = (value: string) => formatForecastDate(value, timezone)
  if (!run.observations.length && !run.predictions.length) return <ForecastState title="No chart data is available">This saved run has no recorded daily deliveries or forecast points to display.</ForecastState>

  return <section className="forecast-chart-panel panel" aria-labelledby="forecast-chart-title">
    <div className="forecast-detail-section-heading"><div><span className="inventory-catalog-icon"><ChartNoAxesCombined size={18} aria-hidden="true" /></span><div><h2 id="forecast-chart-title">Past deliveries and saved estimate</h2><p>The gray line shows past deliveries; the purple dashed line shows the saved estimate.</p></div></div><span className="forecast-chart-uom">{run.uom || 'Synthetic units'} per day</span></div>
    {run.source_type === 'completed_deliveries' && <p className="forecast-demand-note"><CircleHelp size={14} aria-hidden="true" />Completed deliveries are a fulfilled-sales record, not a measure of all customer demand. Stockouts can limit what the history shows.</p>}
    <div className="forecast-chart-legend"><span><i className="is-history" />Completed deliveries</span><span><i className="is-future" />Saved estimate</span>{run.predictions.length > 0 && <span><i className="is-range" />Planning range</span>}</div>
    <div className="forecast-chart-wrap" role="img" aria-label={`Daily completed deliveries and forecast for ${run.product_name}`} data-first-forecast-day={firstPrediction?.day} data-first-forecast-units={firstPrediction ? String(firstPrediction.units) : undefined} data-first-forecast-lower={firstPrediction ? String(firstPrediction.lower_heuristic) : undefined} data-first-forecast-upper={firstPrediction ? String(firstPrediction.upper_heuristic) : undefined}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 22, right: 18, left: 3, bottom: 1 }}>
          <CartesianGrid stroke="#edf0f5" strokeDasharray="3 4" vertical={false} />
          <XAxis dataKey="date" tickFormatter={formatter} tickLine={false} axisLine={false} minTickGap={34} tick={{ fill: '#788198', fontSize: 11 }} />
          <YAxis width={48} tickLine={false} axisLine={false} allowDecimals tick={{ fill: '#788198', fontSize: 11 }} tickFormatter={(value: number) => formatQuantity(value, 0)} />
          <Tooltip content={(props) => <ForecastTooltip active={props.active} payload={props.payload as unknown as ReadonlyArray<{ payload: ForecastChartPoint; dataKey?: string }> | undefined} label={props.label} uom={run.uom || 'example units'} />} />
          <Area dataKey="lower" stackId="heuristic" stroke="none" fill="transparent" isAnimationActive={false} legendType="none" tooltipType="none" />
          <Area dataKey="band" stackId="heuristic" stroke="none" fill="#e9e4ff" fillOpacity={0.82} isAnimationActive={false} legendType="none" tooltipType="none" />
          <Line dataKey="actual" type="monotone" stroke="#5f6d85" strokeWidth={2.2} dot={false} connectNulls={false} isAnimationActive={false} name="Completed deliveries" />
          <Line dataKey="forecast" type="monotone" stroke="#7048ef" strokeWidth={2.6} strokeDasharray="7 5" dot={false} connectNulls={false} isAnimationActive={false} name="Forecast" />
          {firstFutureDate && <ReferenceLine x={firstFutureDate} stroke="#9d8ae8" strokeDasharray="4 4" label={{ value: 'Forecast starts', position: 'insideTopRight', fill: '#6d55bf', fontSize: 11, fontWeight: 650 }} />}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
    <p className="forecast-range-caption">The shaded area is a planning range, not a guarantee.</p>
  </section>
}

function ReviewBadge({ status }: { status: ForecastListRun['review_status'] }) {
  return <span className={`forecast-review is-detail ${status === 'reviewed' ? 'is-reviewed' : 'is-unreviewed'}`} title={status === 'unreviewed' ? 'An inventory manager has not reviewed this saved estimate.' : undefined}>{status === 'reviewed' ? <ShieldCheck size={13} aria-hidden="true" /> : <Clock3 size={13} aria-hidden="true" />}{reviewLabel(status)}</span>
}

function restockSummary(status: ForecastDetailData['restock_guidance']['status']) {
  const messages: Record<ForecastDetailData['restock_guidance']['status'], string> = {
    eligible: 'This saved estimate can inform current restock guidance.',
    not_eligible: 'This saved estimate is not currently used for restock guidance.',
    not_applicable: 'This demonstration example is separate from real restock guidance.',
    restricted: 'Restock eligibility could not be checked for your current access.',
    unavailable: 'This saved estimate is not used for restock guidance right now.',
  }
  return messages[status]
}

function detailEstimateMessage(estimate: ForecastEstimate, run: ForecastDetailData['run']) {
  if (estimate.status === 'available') return ''
  if (estimate.status === 'missing') return 'No saved daily estimate is available for this run.'
  if (estimate.status === 'not_completed') {
    const reasons: Record<ForecastListRun['state'], string> = {
      queued: 'This estimate is waiting to be prepared.',
      running: 'This estimate is still being prepared.',
      completed: 'A total is not available because the saved daily series is incomplete.',
      insufficient_history: 'There is not enough recorded delivery history for this estimate.',
      no_observed_demand: 'No completed deliveries were recorded in the selected history period.',
      failed: 'This estimate could not be calculated.',
    }
    return reasons[run.state]
  }
  if (run.predictions.length) return `A total is not available because only ${count(run.predictions.length)} of ${count(run.horizon_days)} daily estimates are saved.`
  return 'A total is not available because this run has no saved daily estimates.'
}

function ForecastEstimateSummary({ detail, timezone }: { detail: ForecastDetailData; timezone: string }) {
  const { estimate, run, restock_guidance: guidance } = detail
  const isAvailable = estimate.status === 'available'
    && estimate.estimated_units !== false
    && estimate.uom_rounding !== false
    && Boolean(estimate.uom && estimate.date_start && estimate.date_end)
  return <section className="forecast-estimate-summary panel" aria-label="Selected forecast summary">
    <div className="forecast-summary-main">
      <div className="forecast-summary-period"><span>Selected period</span><strong>{count(run.horizon_days)} days</strong><small>{isAvailable ? `${formatForecastDate(estimate.date_start as string, timezone, { year: 'numeric' })} – ${formatForecastDate(estimate.date_end as string, timezone, { year: 'numeric' })}` : 'Saved date range is unavailable'}</small>{isAvailable && <small className="forecast-summary-window">{estimate.window_status === 'ended' ? 'This saved period has ended.' : estimate.window_status === 'in_progress' ? 'This saved period is in progress.' : `This saved period starts ${formatForecastDate(estimate.date_start as string, timezone, { year: 'numeric' })}.`}</small>}</div>
      <div className="forecast-summary-total" aria-live="polite"><span>{isAvailable ? 'Estimated deliveries' : 'Estimate total'}</span>{isAvailable ? <strong data-testid="forecast-estimated-total">{formatEmployeeForecastTotal(estimate.estimated_units as number, estimate.uom_rounding as number, estimate.uom as string)}</strong> : <p data-testid="forecast-estimate-unavailable">{detailEstimateMessage(estimate, run)}</p>}</div>
    </div>
    <p className="forecast-restock-summary"><CircleHelp size={15} aria-hidden="true" />{restockSummary(guidance.status)}</p>
  </section>
}

function EvidenceRow({ label, children }: { label: string; children: ReactNode }) {
  return <div><dt>{label}</dt><dd>{children}</dd></div>
}

function EvaluationDisclosure({ detail, timezone }: { detail: ForecastDetailData; timezone: string }) {
  const run = detail.run
  const coverage = detail.history_coverage
  const canCompare = run.evaluation_status === 'evaluated' || run.evaluation_status === 'baseline_only' || run.evaluation_status === 'intermittent_baseline'
  const coverageMessage = coverage.verified_demo_profile_scoped
    ? coverage.verified_demo_profile_current
      ? `This fictional source profile is verified for ${run.warehouse_name || 'company-wide history'} over the saved dates. It is a fixture-specific exception; normal history coverage settings still apply to other parts.`
      : `The saved profile is scoped to ${run.warehouse_name || 'company-wide history'}, but its current Odoo delivery and return history no longer matches. Restock guidance is unavailable.`
    : coverage.configured
      ? coverage.run_starts_within_coverage
        ? `Run starts on or after the configured complete-history date (${coverage.complete_from}); this is an administrator assertion.`
        : `Run starts before the configured complete-history date (${coverage.complete_from}).`
      : 'A complete-history start date is not configured for this scope.'
  return <details className="forecast-evaluation-disclosure">
    <summary>How was this estimated?</summary>
    <div className="forecast-evaluation-body">
      <p>{run.source_type === 'synthetic_demo' ? 'This chart uses generated demonstration values. It is separate from actual Odoo sales and stock records.' : 'This result uses completed customer deliveries recorded in Odoo. It represents fulfilled sales and can understate demand when stockouts prevent orders from being fulfilled.'}</p>
      <dl className="forecast-provenance-list">
        <EvidenceRow label="Forecast status">{statusLabel(run.state)}</EvidenceRow>
        <EvidenceRow label="Part and warehouse">{run.product_name} · {run.warehouse_name || 'Company-wide history'}</EvidenceRow>
        <EvidenceRow label="Recorded history">{formatForecastDate(run.history_start, timezone, { year: 'numeric' })} – {formatForecastDate(run.history_end, timezone, { year: 'numeric' })}</EvidenceRow>
        <EvidenceRow label="History source">{run.source_label}</EvidenceRow>
        <EvidenceRow label={run.source_type === 'synthetic_demo' ? 'Generated daily values' : 'Completed delivery and return events'}>{run.source_type === 'synthetic_demo' ? `${count(run.history_days)} calendar days` : `${count(run.source_event_count)} source events · ${count(run.history_days)} calendar days`}</EvidenceRow>
        <EvidenceRow label="Days with deliveries">{count(run.nonzero_days)}</EvidenceRow>
        <EvidenceRow label="Saved daily estimates">{count(run.predictions.length)} of {count(run.horizon_days)} days</EvidenceRow>
        <EvidenceRow label="Source cutoff (your local time)">{formatForecastDateTime(run.source_cutoff, timezone)}</EvidenceRow>
        <EvidenceRow label="Source timezone">{run.source_timezone}</EvidenceRow>
        {run.source_snapshot_sha256 && <EvidenceRow label="Source snapshot">{run.source_snapshot_sha256}</EvidenceRow>}
        {run.model_version && <EvidenceRow label="Engine version">{run.model_version}</EvidenceRow>}
        {run.current_stock && <EvidenceRow label={`Current stock — ${run.warehouse_name || 'company-wide'}`}>{formatQuantity(run.current_stock.on_hand)} on hand · {formatQuantity(run.current_stock.odoo_projected)} projected · {run.current_stock.uom}</EvidenceRow>}
        {run.reviewed_by && <EvidenceRow label="Reviewed by">{run.reviewed_by}</EvidenceRow>}
        {run.reviewed_at && <EvidenceRow label="Review date">{formatForecastDateTime(run.reviewed_at, timezone)}</EvidenceRow>}
        <EvidenceRow label="Restock guidance">{detail.restock_guidance.reason}</EvidenceRow>
        <EvidenceRow label="History coverage">{coverageMessage}</EvidenceRow>
      </dl>
      {canCompare ? <dl className="forecast-evaluation-grid">
        <div><dt>Selected method</dt><dd>{methodLabel(run.selected_method)}</dd></div>
        <div><dt>Baseline comparison</dt><dd>{methodLabel(run.baseline_method)}</dd></div>
        <div><dt>Chronological holdout</dt><dd>{count(run.evaluation_days)} days</dd></div>
        {run.demand_pattern && <div><dt>Observed pattern</dt><dd>{run.demand_pattern.replaceAll('_', ' ')}</dd></div>}
        <div><dt>Evaluation result</dt><dd>{run.evaluation_status === 'intermittent_baseline' ? 'Intermittent-sales baseline' : run.evaluation_status === 'baseline_only' ? 'Baseline only' : 'Model compared with baseline'}</dd></div>
        {run.baseline_mae !== false && <div><dt>Baseline MAE</dt><dd>{formatQuantity(run.baseline_mae)} {run.uom || 'example units'} per day</dd></div>}
        {run.ml_mae !== false && <div><dt>Model MAE</dt><dd>{formatQuantity(run.ml_mae)} {run.uom || 'example units'} per day</dd></div>}
      </dl> : <p className="forecast-evaluation-unavailable">Evaluation details are unavailable for this run ({run.evaluation_status || 'not evaluated'}).</p>}
      <p className="forecast-evaluation-caveat">MAE is the average absolute daily error on this run’s chronological holdout. The same holdout helps select the method, so this is comparison evidence for the saved series, not an independent accuracy claim. Lower error is closer on that history window; it does not guarantee future results.</p>
      {run.interval_note && <p className="forecast-evaluation-caveat">{run.interval_note}</p>}
      {run.failure_reason && <div className="forecast-evaluation-copy"><strong>Calculation note</strong><p>{run.failure_reason}</p></div>}
      {run.assumptions && <div className="forecast-evaluation-copy"><strong>Assumptions</strong><p>{run.assumptions}</p></div>}
      {run.limitations && <div className="forecast-evaluation-copy"><strong>Limitations</strong><p>{run.limitations}</p></div>}
      {run.data_provenance && <div className="forecast-evaluation-copy"><strong>Data source details</strong><p>{run.data_provenance}</p></div>}
    </div>
  </details>
}

function ForecastRunDetail({ runId, companyId, session, onSwitchCompany, onSignOut }: WorkspaceSessionValue & { runId: number }) {
  const search = useSearch({ from: '/forecasts/$runId' })
  const view = search.view ?? 'parts'
  const [selectedProduct, setSelectedProduct] = useState<ProductStub | null>(null)
  const detail = useQuery({ queryKey: ['forecast-detail', companyId, runId], queryFn: () => api.forecastDetail(companyId, runId) })
  const run = detail.data?.run
  const company = session.allowed_companies.find((item) => item.id === companyId) ?? session.current_company
  const listRun: ForecastListRun | undefined = run ? {
    id: run.id,
    product_id: run.product_id,
    product_name: run.product_name,
    sku: run.sku,
    warehouse_id: run.warehouse_id,
    warehouse_name: run.warehouse_name,
    horizon_days: run.horizon_days as 7 | 30 | 60,
    history_start: run.history_start,
    history_end: run.history_end,
    source_cutoff: run.source_cutoff,
    created_at: run.created_at,
    source_type: run.source_type,
    state: run.state,
    evaluation_status: run.evaluation_status,
    review_status: run.review_status,
  } : undefined

  return <ForecastWorkspace workspace={{ session, companyId, onSwitchCompany, onSignOut }} activeSection="forecast" selectedProduct={selectedProduct} onSelectProduct={setSelectedProduct}>
    <main className="page-content inventory-page forecasts-page forecast-detail-page">
      <Link to="/forecasts" search={{ view: view === 'history' ? 'history' : 'parts' }} className="forecast-back-link"><ChevronLeft size={16} aria-hidden="true" />Back to forecasts</Link>
      {detail.isError && !detail.data ? <ForecastError error={detail.error} onRetry={() => void detail.refetch()} /> : detail.isPending && !detail.data ? <ForecastLoading detail /> : detail.data && run && listRun ? <>
        <div className="forecast-detail-heading"><div><div className="inventory-eyebrow"><ChartNoAxesCombined size={14} aria-hidden="true" /> Forecast for this part</div><h1>{run.product_name}</h1><p>SKU {run.sku} · {run.warehouse_name || 'Company-wide history'} · {company.name}</p></div><div className="forecast-detail-badges"><ForecastPill run={listRun} /><ReviewBadge status={run.review_status} /></div></div>
        {run.source_type === 'synthetic_demo' && <div className="forecast-demo-banner" role="note"><Sparkles size={16} aria-hidden="true" /><div><strong>Synthetic showroom example</strong><p>Generated values for demonstration only. This chart is not based on Atlas delivery history and is never used for real stock or restock guidance.</p></div></div>}
        <ForecastEstimateSummary detail={detail.data} timezone={session.user.timezone} />
        <ForecastChart run={run} timezone={session.user.timezone} />
        <section className="forecast-evaluation-panel panel"><div className="forecast-detail-section-heading"><div><span className="inventory-catalog-icon"><CircleHelp size={18} aria-hidden="true" /></span><div><h2>Estimate details</h2><p>Source, review and evaluation evidence, when you need it.</p></div></div></div><EvaluationDisclosure detail={detail.data} timezone={session.user.timezone} /></section>
        {run.product_id && <div className="forecast-detail-actions"><button className="forecast-product-action" type="button" onClick={() => setSelectedProduct({ id: run.product_id as number, name: run.product_name, sku: run.sku, reference: '', category: '' })}><Boxes size={15} aria-hidden="true" />View part details</button><span>Part data opens in the read-only Inventory detail view.</span></div>}
      </> : null}
    </main>
  </ForecastWorkspace>
}

function ForecastWorkspace({ workspace, activeSection, selectedProduct, onSelectProduct, children }: {
  workspace: WorkspaceSessionValue; activeSection: DashboardSection; selectedProduct: ProductStub | null; onSelectProduct: (product: ProductStub | null) => void; children: ReactNode
}) {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const navigate = useNavigate()
  const { session, companyId, onSwitchCompany, onSignOut } = workspace

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
    if (section === 'forecast') void navigate({ to: '/forecasts' })
  }

  return <>
    <DashboardShell collapsed={collapsed} onToggleCollapsed={() => setCollapsed((value) => !value)} activeSection={activeSection} onNavigate={navigateTo} onUnavailable={() => undefined} onOpenSearch={() => setSearchOpen(true)} mobileNavOpen={mobileNavOpen} onMobileNavChange={setMobileNavOpen} session={session} companyId={companyId} onSwitchCompany={onSwitchCompany} onSignOut={onSignOut}>{children}</DashboardShell>
    <ProductSearchDialog companyId={companyId} open={searchOpen} onOpenChange={setSearchOpen} onSelectProduct={(product) => { onSelectProduct({ id: product.id, name: product.name, sku: product.sku, reference: product.reference, category: product.category }); setSearchOpen(false) }} />
    {selectedProduct && <InventoryDetailSheet product={{ product_id: selectedProduct.id, name: selectedProduct.name, sku: selectedProduct.sku, reference: selectedProduct.reference, category: selectedProduct.category }} companyId={companyId} locale={session.user.locale} timezone={session.user.timezone} onClose={() => onSelectProduct(null)} />}
  </>
}

export function ForecastsPage() {
  return <WorkspaceSession>{(value) => <ForecastOverview {...value} key={value.companyId} />}</WorkspaceSession>
}

export function ForecastDetailPage({ runId }: { runId: number }) {
  return <WorkspaceSession>{(value) => <ForecastRunDetail {...value} runId={runId} key={`${value.companyId}-${runId}`} />}</WorkspaceSession>
}
