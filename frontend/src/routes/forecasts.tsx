import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import {
  AlertCircle, Boxes, CalendarDays, ChartNoAxesCombined,
  ChevronLeft, ChevronRight, CircleHelp, Clock3, Database, PackageSearch,
  Search, ShieldCheck, Sparkles, Warehouse as WarehouseIcon,
} from 'lucide-react'
import {
  Area, CartesianGrid, ComposedChart, Line, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { ApiError, api, type ForecastsRequest } from '@/api/client'
import type { ForecastDetailData, ForecastListRun, ForecastsData } from '@/api/contracts'
import { DashboardShell, type DashboardSection } from '@/components/gate-one/dashboard-shell'
import { InventoryDetailSheet } from '@/components/inventory/inventory-detail-sheet'
import { ProductSearchDialog, type ProductSearchItem } from '@/components/gate-two/product-search-dialog'
import { WorkspaceSession, type WorkspaceSessionValue } from '@/components/workspace-session'
import { useDebounce } from '@/hooks/use-debounce'
import { formatQuantity } from '@/lib/dashboard'
import { buildForecastChartPoints, formatForecastDate, formatForecastDateTime, formatForecastTime, type ForecastChartPoint } from '@/lib/forecasts'
import '@/styles/inventory.css'
import '@/styles/forecasts.css'

const PAGE_SIZE = 25
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

function reviewLabel(status: ForecastListRun['review_status'], sourceType?: ForecastListRun['source_type']) {
  if (status === 'reviewed') return 'Reviewed'
  return sourceType === 'synthetic_demo' ? 'Not reviewed' : 'Needs review'
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
  return <ForecastState title={forbidden ? 'Forecast history is restricted' : 'Forecasts could not be loaded'} icon={AlertCircle}>
    {forbidden ? 'Your current Odoo role cannot read the requested forecast history for this company. Ask your administrator to review your access.' : error.message}
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

function ForecastMobileCard({ run, timezone }: { run: ForecastListRun; timezone: string }) {
  return <Link className="forecast-mobile-card" to="/forecasts/$runId" params={{ runId: String(run.id) }} aria-label={`Open forecast for ${run.product_name}, SKU ${run.sku}`}>
    <div className="forecast-mobile-card-top"><span className="forecast-mobile-part"><strong>{run.product_name}</strong><small>SKU {run.sku}</small></span><ChevronRight size={17} aria-hidden="true" /></div>
    <div className="forecast-mobile-badges"><ForecastPill run={run} /><span className={`forecast-review ${run.review_status === 'reviewed' ? 'is-reviewed' : 'is-unreviewed'}`}>{reviewLabel(run.review_status, run.source_type)}</span></div>
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

function ForecastOverview({ companyId, session, onSwitchCompany, onSignOut }: WorkspaceSessionValue) {
  const [query, setQuery] = useState('')
  const [warehouseId, setWarehouseId] = useState<number | undefined>()
  const [horizonDays, setHorizonDays] = useState<HorizonFilter>('all')
  const [state, setState] = useState<RunState>('all')
  const [reviewStatus, setReviewStatus] = useState<ReviewFilter>('all')
  const [sourceType, setSourceType] = useState<SourceFilter>('all')
  const [page, setPage] = useState(1)
  const [selectedProduct, setSelectedProduct] = useState<ProductStub | null>(null)
  const debouncedQuery = useDebounce(query.trim(), 250)
  const filters: ForecastsRequest = { query: debouncedQuery, warehouseId, horizonDays, state, reviewStatus, sourceType, page, pageSize: PAGE_SIZE }
  const forecasts = useQuery({ queryKey: ['forecasts', companyId, filters], queryFn: () => api.forecasts(companyId, filters), placeholderData: keepPreviousData })
  const company = session.allowed_companies.find((item) => item.id === companyId) ?? session.current_company
  const filterActive = Boolean(query || warehouseId || horizonDays !== 'all' || state !== 'all' || reviewStatus !== 'all' || sourceType !== 'all')

  function clearFilters() {
    setQuery(''); setWarehouseId(undefined); setHorizonDays('all'); setState('all'); setReviewStatus('all'); setSourceType('all'); setPage(1)
  }

  return <ForecastWorkspace workspace={{ session, companyId, onSwitchCompany, onSignOut }} activeSection="forecast" selectedProduct={selectedProduct} onSelectProduct={setSelectedProduct}>
    <main className="page-content inventory-page forecasts-page">
      <div className="page-heading inventory-page-heading forecasts-page-heading">
        <div><div className="inventory-eyebrow"><ChartNoAxesCombined size={14} aria-hidden="true" /> Demand planning</div><h1>Forecasts</h1><p>Review completed deliveries and saved demand estimates for parts at {company.name}.</p></div>
        <span className="warehouse-readonly-mark"><ShieldCheck size={14} aria-hidden="true" /> Read-only view</span>
      </div>
      {forecasts.isError && !forecasts.data ? <ForecastError error={forecasts.error} onRetry={() => void forecasts.refetch()} /> : forecasts.isPending && !forecasts.data ? <ForecastLoading /> : forecasts.data ? <>
        {forecasts.data.access_note && <p className="forecast-access-note" role="note"><CircleHelp size={15} aria-hidden="true" />{forecasts.data.access_note}</p>}
        <section className="forecast-catalog panel" aria-labelledby="forecast-list-title">
          <div className="forecast-catalog-heading"><div className="inventory-catalog-title"><span className="inventory-catalog-icon"><ChartNoAxesCombined size={18} aria-hidden="true" /></span><div><h2 id="forecast-list-title">Saved forecasts</h2><p>{forecasts.data.pagination.total_count === 1 ? '1 forecast matches your filters' : `${count(forecasts.data.pagination.total_count)} forecasts match your filters`}. Results include saved runs within this company.</p></div></div><span className="inventory-live-mark"><i aria-hidden="true" /> Live Odoo data</span></div>
          <div className="forecast-filter-area">
            <label className="inventory-search-field"><Search size={16} aria-hidden="true" /><span className="sr-only">Search forecasts by part name or SKU</span><input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1) }} placeholder="Search part name or SKU…" type="search" autoComplete="off" />{query && <button type="button" aria-label="Clear forecast search" onClick={() => { setQuery(''); setPage(1) }}>Clear</button>}</label>
            <div className="forecast-filter-controls">
              <label className="inventory-select-wrap"><span>Warehouse</span><select aria-label="Filter forecasts by warehouse" value={warehouseId ?? ''} onChange={(event) => { setWarehouseId(event.target.value ? Number(event.target.value) : undefined); setPage(1) }}><option value="">All warehouses</option>{forecasts.data.warehouse_options.map((warehouse) => <option key={warehouse.id} value={warehouse.id}>{warehouse.name}</option>)}</select></label>
              <label className="inventory-select-wrap"><span>Horizon</span><select aria-label="Filter forecasts by horizon" value={horizonDays} onChange={(event) => { setHorizonDays(event.target.value === 'all' ? 'all' : Number(event.target.value) as 7 | 30 | 60); setPage(1) }}><option value="all">All horizons</option><option value="7">7 days</option><option value="30">30 days</option><option value="60">60 days</option></select></label>
              <label className="inventory-select-wrap"><span>Run status</span><select aria-label="Filter forecasts by run status" value={state} onChange={(event) => { setState(event.target.value as RunState); setPage(1) }}><option value="all">All statuses</option><option value="queued">Waiting to run</option><option value="running">Calculating</option><option value="completed">Calculated</option><option value="insufficient_history">Not enough history</option><option value="no_observed_demand">No deliveries recorded</option><option value="failed">Could not calculate</option></select></label>
              <label className="inventory-select-wrap"><span>Review</span><select aria-label="Filter forecasts by review status" value={reviewStatus} onChange={(event) => { setReviewStatus(event.target.value as ReviewFilter); setPage(1) }}><option value="all">All review states</option><option value="reviewed">Reviewed</option><option value="unreviewed">Needs review</option></select></label>
              <label className="inventory-select-wrap"><span>Source</span><select aria-label="Filter forecasts by source" value={sourceType} onChange={(event) => { setSourceType(event.target.value as SourceFilter); setPage(1) }}><option value="all">All sources</option><option value="completed_deliveries">Completed deliveries</option><option value="synthetic_demo">Synthetic showroom</option></select></label>
              {filterActive && <button className="forecast-clear-filters" type="button" onClick={clearFilters}>Clear filters</button>}
            </div>
          </div>
          {forecasts.data.warehouse_options_limited && <p className="forecast-filter-note" role="note">This company has {count(forecasts.data.warehouse_count)} warehouses. Choose from the first 100 alphabetically; enter a warehouse-specific link only if your administrator has granted access.</p>}
          {forecasts.data.runs.length ? <>
            <div className="forecast-table-wrap"><table className="forecast-table"><thead><tr><th>Part</th><th>Warehouse / source</th><th>Horizon / history</th><th>Run status</th><th>Review</th><th>Saved</th><th><span className="sr-only">Details</span></th></tr></thead><tbody>{forecasts.data.runs.map((run) => <tr key={run.id}><td><ForecastRowPart run={run} /></td><td><span className="forecast-table-scope">{run.warehouse_name || 'Company-wide'}</span><small className="forecast-table-source">{run.source_type === 'synthetic_demo' ? 'Synthetic showroom' : 'Completed deliveries'}</small></td><td><strong>{run.horizon_days} days</strong><small>{formatForecastDate(run.history_start, session.user.timezone)} – {formatForecastDate(run.history_end, session.user.timezone)}</small></td><td><ForecastPill run={run} /></td><td><span className={`forecast-review ${run.review_status === 'reviewed' ? 'is-reviewed' : 'is-unreviewed'}`}>{reviewLabel(run.review_status, run.source_type)}</span></td><td><strong data-testid="forecast-saved-date">{formatForecastDate(run.created_at, session.user.timezone, { year: 'numeric' })}</strong><small data-testid="forecast-saved-time">{formatForecastTime(run.created_at, session.user.timezone)}</small></td><td><Link className="forecast-table-open" to="/forecasts/$runId" params={{ runId: String(run.id) }} aria-label={`Open forecast for ${run.product_name}, SKU ${run.sku}`}><ChevronRight size={17} aria-hidden="true" /></Link></td></tr>)}</tbody></table></div>
            <div className="forecast-mobile-list">{forecasts.data.runs.map((run) => <ForecastMobileCard key={run.id} run={run} timezone={session.user.timezone} />)}</div>
            <ForecastPagination data={forecasts.data} onPage={setPage} />
          </> : <div className="forecast-empty"><span className="inventory-state-icon"><PackageSearch size={22} aria-hidden="true" /></span><h2>{filterActive ? 'No forecasts match these filters' : 'No saved forecasts yet'}</h2><p>{filterActive ? 'Try a different part, warehouse, status, or horizon. You can clear the filters to see all saved runs available to your role.' : 'Forecast runs will appear here after they have been created through the separately approved forecasting workflow.'}</p>{filterActive && <button className="inventory-secondary-button" type="button" onClick={clearFilters}>Clear filters</button>}</div>}
          {forecasts.isFetching && <div className="forecast-fetching" role="status">Updating forecast results…</div>}
        </section>
      </> : null}
    </main>
  </ForecastWorkspace>
}

function ForecastRowPart({ run }: { run: ForecastListRun }) {
  return <Link className="forecast-table-part" to="/forecasts/$runId" params={{ runId: String(run.id) }}><span className="forecast-row-icon"><Boxes size={16} aria-hidden="true" /></span><span><strong>{run.product_name}</strong><small>SKU {run.sku}</small></span></Link>
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
    <span className="forecast-tooltip-key is-forecast">Forecasted deliveries <b>{point.forecast === null ? '—' : `${formatQuantity(point.forecast)} ${uom}`}</b></span>
    {point.lower !== null && point.band !== null && <small>Heuristic range {formatQuantity(point.lower)}–{formatQuantity(point.lower + point.band)} {uom}</small>}
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
    <div className="forecast-detail-section-heading"><div><span className="inventory-catalog-icon"><ChartNoAxesCombined size={18} aria-hidden="true" /></span><div><h2 id="forecast-chart-title">Delivered history and forecast</h2><p>Completed customer deliveries are shown as recorded; the forecast begins after the history window.</p></div></div><span className="forecast-chart-uom">{run.uom || 'Synthetic units'} per day</span></div>
    {run.source_type === 'completed_deliveries' && <p className="forecast-demand-note"><CircleHelp size={14} aria-hidden="true" />Completed deliveries are a fulfilled-sales record, not a measure of all customer demand. Stockouts can limit what the history shows.</p>}
    <div className="forecast-chart-legend"><span><i className="is-history" />Completed deliveries</span><span><i className="is-future" />Forecast</span>{run.predictions.length > 0 && <span><i className="is-range" />Heuristic range</span>}</div>
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
    <p className="forecast-range-caption">The shaded range is a heuristic display aid. It is not a statistical confidence guarantee.</p>
  </section>
}

function ReviewBadge({ status, sourceType }: { status: ForecastListRun['review_status']; sourceType: ForecastListRun['source_type'] }) {
  return <span className={`forecast-review is-detail ${status === 'reviewed' ? 'is-reviewed' : 'is-unreviewed'}`}>{status === 'reviewed' ? <ShieldCheck size={13} aria-hidden="true" /> : <Clock3 size={13} aria-hidden="true" />}{reviewLabel(status, sourceType)}</span>
}

function GuidancePanel({ data }: { data: ForecastDetailData }) {
  const guidance = data.restock_guidance
  const state = guidance.status === 'eligible' ? 'is-eligible'
    : guidance.status === 'restricted' ? 'is-restricted'
      : guidance.status === 'not_applicable' ? 'is-demo'
        : 'is-blocked'
  const title = guidance.status === 'eligible' ? 'Used for current restock guidance'
    : guidance.status === 'not_applicable' ? 'Not used for real stock guidance'
      : guidance.status === 'restricted' ? 'Restock eligibility could not be checked'
        : 'Not used for current restock guidance'
  return <section className={`forecast-guidance panel ${state}`} aria-labelledby="forecast-guidance-title">
    <div className="forecast-guidance-icon">{guidance.status === 'eligible' ? <ShieldCheck size={19} aria-hidden="true" /> : <CircleHelp size={19} aria-hidden="true" />}</div>
    <div><h2 id="forecast-guidance-title">{title}</h2><p>{guidance.reason}</p></div>
  </section>
}

function EvaluationDisclosure({ detail }: { detail: ForecastDetailData }) {
  const run = detail.run
  const canCompare = run.evaluation_status === 'evaluated' || run.evaluation_status === 'baseline_only' || run.evaluation_status === 'intermittent_baseline'
  return <details className="forecast-evaluation-disclosure">
    <summary>How this forecast was calculated</summary>
    <div className="forecast-evaluation-body">
      <p>{run.source_type === 'synthetic_demo' ? 'This chart uses generated demonstration values. It is separate from actual Odoo sales and stock records.' : 'This result uses completed customer deliveries recorded in Odoo. It represents fulfilled sales and can understate demand when stockouts prevent orders from being fulfilled.'}</p>
      {canCompare ? <dl className="forecast-evaluation-grid">
        <div><dt>Selected method</dt><dd>{methodLabel(run.selected_method)}</dd></div>
        <div><dt>Baseline comparison</dt><dd>{methodLabel(run.baseline_method)}</dd></div>
        <div><dt>Chronological holdout</dt><dd>{count(run.evaluation_days)} days</dd></div>
        <div><dt>Evaluation result</dt><dd>{run.evaluation_status === 'intermittent_baseline' ? 'Intermittent-sales baseline' : run.evaluation_status === 'baseline_only' ? 'Baseline only' : 'Model compared with baseline'}</dd></div>
        {run.baseline_mae !== false && <div><dt>Baseline MAE</dt><dd>{formatQuantity(run.baseline_mae)} {run.uom || 'example units'} per day</dd></div>}
        {run.ml_mae !== false && <div><dt>Model MAE</dt><dd>{formatQuantity(run.ml_mae)} {run.uom || 'example units'} per day</dd></div>}
      </dl> : <p className="forecast-evaluation-unavailable">Evaluation details are unavailable for this run ({run.evaluation_status || 'not evaluated'}).</p>}
      <p className="forecast-evaluation-caveat">MAE is the average absolute daily error on this run’s chronological holdout. The same holdout helps select the method, so this is comparison evidence for the saved series, not an independent accuracy claim. Lower error is closer on that history window; it does not guarantee future results.</p>
      {run.interval_note && <p className="forecast-evaluation-caveat">{run.interval_note}</p>}
      {run.assumptions && <div className="forecast-evaluation-copy"><strong>Assumptions</strong><p>{run.assumptions}</p></div>}
      {run.limitations && <div className="forecast-evaluation-copy"><strong>Limitations</strong><p>{run.limitations}</p></div>}
      {run.data_provenance && <div className="forecast-evaluation-copy"><strong>Data source</strong><p>{run.data_provenance}</p></div>}
    </div>
  </details>
}

function ForecastRunDetail({ runId, companyId, session, onSwitchCompany, onSignOut }: WorkspaceSessionValue & { runId: number }) {
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
      <Link to="/forecasts" className="forecast-back-link"><ChevronLeft size={16} aria-hidden="true" />All forecasts</Link>
      {detail.isError && !detail.data ? <ForecastError error={detail.error} onRetry={() => void detail.refetch()} /> : detail.isPending && !detail.data ? <ForecastLoading detail /> : detail.data && run && listRun ? <>
        <div className="forecast-detail-heading"><div><div className="inventory-eyebrow"><ChartNoAxesCombined size={14} aria-hidden="true" /> Saved demand estimate</div><h1>{run.product_name}</h1><p>SKU {run.sku} · {company.name}{run.warehouse_name ? ` · ${run.warehouse_name}` : ' · Company-wide history'}</p></div><div className="forecast-detail-badges"><ForecastPill run={listRun} /><ReviewBadge status={run.review_status} sourceType={run.source_type} /></div></div>
        {run.source_type === 'synthetic_demo' && <div className="forecast-demo-banner" role="note"><Sparkles size={16} aria-hidden="true" /><div><strong>Synthetic showroom example</strong><p>Generated values for demonstration only. This chart is not based on Atlas delivery history and is never used for real stock or restock guidance.</p></div></div>}
        <div className="forecast-detail-facts" aria-label="Forecast details">
          <article><span>Forecast period</span><strong>{count(run.horizon_days)} days</strong></article>
          <article><span>Recorded history</span><strong>{formatForecastDate(run.history_start, session.user.timezone)} – {formatForecastDate(run.history_end, session.user.timezone)}</strong></article>
          <article><span>Inventory unit</span><strong>{run.uom || 'Synthetic example units'}</strong></article>
          <article><span>Saved</span><strong>{formatForecastDateTime(run.created_at, session.user.timezone)}</strong></article>
          <article><span>Source cutoff</span><strong>{formatForecastDateTime(run.source_cutoff, session.user.timezone)}</strong></article>
        </div>
        {run.failure_reason && run.state !== 'completed' && <div className="forecast-run-reason" role="note"><AlertCircle size={16} aria-hidden="true" /><span>{run.failure_reason}</span></div>}
        <ForecastChart run={run} timezone={session.user.timezone} />
        <div className="forecast-detail-lower-grid">
          <GuidancePanel data={detail.data} />
          <section className="forecast-provenance-panel panel" aria-labelledby="forecast-source-title">
            <div className="forecast-detail-section-heading"><div><span className="inventory-catalog-icon"><Database size={18} aria-hidden="true" /></span><div><h2 id="forecast-source-title">History and review</h2><p>Recorded source and review details for this exact run.</p></div></div></div>
            <dl className="forecast-provenance-list">
              <div><dt>History source</dt><dd>{run.source_label}</dd></div>
              <div><dt>{run.source_type === 'synthetic_demo' ? 'Generated daily values' : 'Completed delivery and return events'}</dt><dd>{run.source_type === 'synthetic_demo' ? `${count(run.history_days)} calendar days` : `${count(run.source_event_count)} source events · ${count(run.history_days)} calendar days`}</dd></div>
              <div><dt>Days with deliveries</dt><dd>{count(run.nonzero_days)}</dd></div>
              <div><dt>Source cutoff</dt><dd>{formatForecastDateTime(run.source_cutoff, session.user.timezone)} (your local time)</dd></div>
              {run.review_status === 'reviewed' && <div><dt>Reviewed by</dt><dd>{run.reviewed_by || 'Inventory manager'}</dd></div>}
              {run.reviewed_at && <div><dt>Review date</dt><dd>{formatForecastDateTime(run.reviewed_at, session.user.timezone)}</dd></div>}
            </dl>
            {run.source_type === 'completed_deliveries' && <p className={`forecast-coverage-note${detail.data.history_coverage.configured && detail.data.history_coverage.run_starts_within_coverage ? ' is-covered' : ''}`}><CircleHelp size={14} aria-hidden="true" />{detail.data.history_coverage.configured ? detail.data.history_coverage.run_starts_within_coverage ? `The run starts on or after the current configured complete-history date (${detail.data.history_coverage.complete_from}). This setting is an administrator assertion.` : `The run starts before the currently configured complete-history date (${detail.data.history_coverage.complete_from}).` : 'A complete-history start date is not currently configured for this scope.'}</p>}
          </section>
        </div>
        <section className="forecast-evaluation-panel panel"><div className="forecast-detail-section-heading"><div><span className="inventory-catalog-icon"><CircleHelp size={18} aria-hidden="true" /></span><div><h2>Evaluation and limitations</h2><p>Method evidence is available on demand.</p></div></div></div><EvaluationDisclosure detail={detail.data} /></section>
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
