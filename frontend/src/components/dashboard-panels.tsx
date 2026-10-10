import { lazy, Suspense, useMemo, useState } from 'react'
import {
  AlertTriangle, Boxes, CircleCheck, Info, PackageCheck, PackageMinus, PackageSearch,
  RefreshCw, Sparkles, TrendingUp, ClipboardList,
} from 'lucide-react'
import type { DashboardData, ForecastData, RestockData } from '@/api/contracts'
import { combineDemandHistory, formatQuantity } from '@/lib/dashboard'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'

const HEALTH_COLORS: Record<string, string> = { healthy: '#36a17b', low: '#dfa841', out: '#d56a74' }
const ForecastPlot = lazy(() => import('@/components/charts/forecast-plot'))
const InventoryHealthChart = lazy(() => import('@/components/charts/inventory-health-chart'))

export function KpiGrid({ data, restock }: { data: DashboardData; restock?: RestockData }) {
  const assessmentNote = data.inventory_health.complete
    ? 'Across tracked parts'
    : `Assessment sample of ${formatQuantity(data.inventory_health.sampled_products)} parts`
  const priority = restock
    ? `${restock.summary.complete ? '' : '≥'}${formatQuantity(restock.summary.priority_locations, 0)}`
    : '—'
  const cards = [
    { label: 'Total SKUs', value: formatQuantity(data.kpis.tracked_products, 0), note: 'Tracked automotive parts', color: 'violet', icon: Boxes },
    { label: 'In stock', value: formatQuantity(data.kpis.in_stock, 0), note: assessmentNote, color: 'green', icon: PackageCheck },
    { label: 'Low stock', value: formatQuantity(data.kpis.low_stock, 0), note: assessmentNote, color: 'amber', icon: PackageSearch },
    { label: 'Out of stock', value: formatQuantity(data.kpis.out_of_stock, 0), note: assessmentNote, color: 'red', icon: PackageMinus },
    { label: 'At risk', value: priority, note: restock?.summary.complete ? 'Locations needing review' : 'At least this many need review', color: 'violet', icon: AlertTriangle },
  ]

  return (
    <section className="kpi-grid" aria-label="Inventory summary">
      {cards.map(({ label, value, note, color, icon: Icon }) => (
        <article className="kpi-card" key={label}>
          <div className="kpi-top"><span className="kpi-label">{label}</span><span className={`kpi-icon ${color}`}><Icon size={17} strokeWidth={1.9} /></span></div>
          <div className="kpi-value">{value}</div>
          <div className="kpi-foot">{note}</div>
        </article>
      ))}
    </section>
  )
}

function ChartUnavailable({ title, message }: { title: string; message: string }) {
  return (
    <div className="chart-unavailable" role="status">
      <span className="chart-unavailable-icon"><AlertTriangle size={17} /></span>
      <strong>{title}</strong>
      <p>{message}</p>
    </div>
  )
}

export function ForecastPanel({ forecast, horizonDays, onHorizonChange }: {
  forecast: ForecastData
  horizonDays: number
  onHorizonChange: (days: number) => void
}) {
  if (forecast.status !== 'available') {
    return (
      <section className="panel forecast-panel" aria-labelledby="forecast-title">
        <div className="panel-header premium-panel-header">
          <div className="panel-heading">
            <div className="panel-title-row"><Sparkles size={18} className="panel-accent-icon" /><h2 id="forecast-title" className="panel-title">Demand Forecast</h2></div>
            <p className="panel-subtitle">Recent sales with a short-term outlook</p>
          </div>
          <select className="compact-control" value={horizonDays} onChange={(event) => onHorizonChange(Number(event.target.value))} aria-label="Forecast horizon">
            <option value={7}>7 days</option><option value={30}>30 days</option><option value={60}>60 days</option>
          </select>
        </div>
        <ChartUnavailable title="Forecast not available" message={forecast.message} />
      </section>
    )
  }

  const run = forecast.forecast
  const chartData = combineDemandHistory(run)
  return (
    <section className="panel forecast-panel" aria-labelledby="forecast-title">
      <div className="panel-header premium-panel-header">
        <div className="panel-heading">
          <div className="panel-title-row"><Sparkles size={18} className="panel-accent-icon" /><h2 id="forecast-title" className="panel-title">Demand Forecast</h2></div>
          <p className="panel-subtitle">Historical demand and the next {run.horizon_days} days</p>
        </div>
        <div className="forecast-controls">
          <span className="compact-control product-control" title={run.product_name}>{run.product_name}</span>
          <select className="compact-control" value={horizonDays} onChange={(event) => onHorizonChange(Number(event.target.value))} aria-label="Forecast horizon">
            <option value={7}>7 days</option><option value={30}>30 days</option><option value={60}>60 days</option>
          </select>
        </div>
      </div>
      {chartData.length ? (
        <div className="chart-area" role="img" aria-label={`Daily units for ${run.product_name}; observed delivery history followed by a forecast with an uncertainty range.`}>
          <Suspense fallback={<div className="chart-loading" role="status">Preparing demand chart…</div>}>
            <ForecastPlot data={chartData} uom={run.uom} />
          </Suspense>
        </div>
      ) : <ChartUnavailable title="No dated points to display" message="This saved forecast has no history or projection points for the selected window." />}
      <div className="chart-legend" aria-label="Chart key">
        <span className="legend-item"><span className="legend-line actual" /> Historical demand</span>
        <span className="legend-item"><span className="legend-line" /> Forecast</span>
        <span className="legend-item"><span className="legend-band" /> Uncertainty range</span>
      </div>
      <div className="forecast-footer">
        <p className="forecast-context">{run.warehouse_name || 'All warehouses'} · Planning estimate; actual demand may differ.</p>
        <details className="forecast-details">
          <summary aria-label="About this demand estimate" title="About this demand estimate"><Info size={15} /></summary>
          <div className="forecast-details-panel">
            <strong>About this estimate</strong>
            <p>{run.review_status === 'reviewed' ? 'Reviewed forecast' : 'Saved forecast'}. Source: {run.source_label}. {run.limitations}</p>
          </div>
        </details>
      </div>
    </section>
  )
}

export function InventoryHealthPanel({ data }: { data: DashboardData }) {
  const categories = data.inventory_health.categories
  const assessed = categories.reduce((sum, item) => sum + item.count, 0)
  const nonEmpty = categories.filter((item) => item.count > 0)

  return (
    <section className="panel health-panel" aria-labelledby="health-title">
      <div className="panel-header">
        <div className="panel-heading"><h2 id="health-title" className="panel-title">Inventory Health</h2><p className="panel-subtitle">Current stock against safety levels</p></div>
      </div>
      <div className="health-body">
        <div className={`health-chart-wrap ${assessed ? '' : 'health-chart-empty'}`} role="img" aria-label={`${formatQuantity(assessed, 0)} assessed parts: ${categories.map((item) => `${item.count} ${item.label.toLowerCase()}`).join(', ')}`}>
          {assessed > 0 && (
            <Suspense fallback={<div className="health-chart-loading" role="status">Loading chart…</div>}>
              <InventoryHealthChart categories={nonEmpty} colors={HEALTH_COLORS} />
            </Suspense>
          )}
          <div className="health-center"><strong>{formatQuantity(assessed, 0)}</strong><span>Total SKUs</span></div>
        </div>
        <div className="health-legend">
          {categories.map((item) => (
            <div className="health-row" key={item.key}>
              <span className="health-row-label"><span className="health-dot" style={{ backgroundColor: HEALTH_COLORS[item.key] }} />{item.label}</span>
              <strong>{formatQuantity(item.count, 0)}</strong>
              <span className="health-share">{assessed ? `${Math.round(item.count / assessed * 100)}%` : '0%'}</span>
            </div>
          ))}
        </div>
        {!data.inventory_health.complete && (
          <p className="coverage-note" role="note">Stock health covers {formatQuantity(assessed, 0)} of {formatQuantity(data.inventory_health.total_tracked, 0)} tracked parts. The summary is partial.</p>
        )}
      </div>
    </section>
  )
}

export function InsightCards({ data, forecast, restock }: {
  data: DashboardData
  forecast?: ForecastData
  restock?: RestockData
}) {
  const expectedDemand = useMemo(() => {
    if (!forecast || forecast.status !== 'available') return null
    return Math.round(forecast.forecast.predictions.reduce((sum, point) => sum + point.units, 0))
  }, [forecast])
  const forecastName = forecast?.status === 'available' ? forecast.forecast.product_name : null
  const restockCount = restock?.summary.reorder_suggestions ?? 0
  const atRiskCount = restock?.summary.priority_locations ?? 0

  const cards = [
    {
      icon: TrendingUp,
      title: 'Demand outlook',
      body: expectedDemand !== null && forecastName
        ? `${forecastName} is expected to move about ${expectedDemand} units over the selected horizon.`
        : 'No reviewed demand forecast is available yet for this dashboard.',
    },
    {
      icon: ClipboardList,
      title: 'Restock suggested',
      body: restock
        ? `${restock.summary.complete ? '' : 'At least '}${restockCount} stock positions have a suggested reorder quantity.`
        : 'Restock guidance is still loading.',
    },
    {
      icon: AlertTriangle,
      title: 'Stock attention',
      body: atRiskCount
        ? `${restock?.summary.complete ? '' : 'At least '}${atRiskCount} product–warehouse positions need review.`
        : data.kpis.low_stock
          ? `${data.kpis.low_stock} tracked parts are below their safety level.`
          : 'No current stock risks are flagged in the available data.',
    },
  ]

  return (
    <section className="insights-panel panel" aria-labelledby="insights-title">
      <div className="insights-heading">
        <div className="panel-title-row"><Sparkles size={18} className="panel-accent-icon" /><h2 id="insights-title" className="panel-title">Insights &amp; Recommendations</h2></div>
      </div>
      <div className="insight-grid">
        {cards.map(({ icon: Icon, title, body }) => (
          <article className="insight-card" key={title}>
            <span className="insight-icon"><Icon size={18} /></span>
            <div><strong>{title}</strong><p>{body}</p></div>
          </article>
        ))}
      </div>
    </section>
  )
}

function RiskStatusIcon({ status }: { status: string }) {
  const out = status === 'out'
  return <span className={`alert-icon ${out ? 'out' : 'low'}`}><AlertTriangle size={15} /></span>
}

export function RestockPanel({ data, warehouseId, onWarehouseChange }: {
  data: RestockData
  warehouseId?: number
  onWarehouseChange: (warehouseId?: number) => void
}) {
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const selected = data.items.find((item) => item.key === selectedKey)
  const emptyTitle = data.coverage.complete ? 'No priority stock alerts' : 'No priority alerts found in this scan'
  const emptyCopy = data.coverage.complete
    ? 'No current inventory positions are flagged for reorder review.'
    : 'The reviewed portion has no priority items. The remaining catalog still needs a scan.'

  return (
    <>
      <section className="panel restock-panel" aria-labelledby="restock-title">
        <div className="panel-header restock-header">
          <div className="panel-heading">
            <div className="panel-title-row"><ClipboardList size={18} className="panel-accent-icon" /><h2 id="restock-title" className="panel-title">Reorder Recommendations</h2></div>
            <p className="panel-subtitle">Read-only suggestions from current stock, suppliers, and reorder rules.</p>
          </div>
          {data.warehouses.length > 1 && (
            <label>
              <span className="sr-only">Filter stock alerts by warehouse</span>
              <select className="warehouse-filter" value={warehouseId ?? ''} onChange={(event) => onWarehouseChange(event.target.value ? Number(event.target.value) : undefined)}>
                <option value="">All warehouses</option>
                {data.warehouses.map((warehouse) => <option value={warehouse.id} key={warehouse.id}>{warehouse.name}</option>)}
              </select>
            </label>
          )}
        </div>
        {data.items.length ? (
          <div className="reorder-table" role="table" aria-label="Reorder recommendations">
            <div className="reorder-head" role="row">
              <span>Part</span><span>Warehouse</span><span>Supplier</span><span>On hand</span><span>Suggested</span><span>Risk</span><span aria-hidden="true" />
            </div>
            {data.items.map((item) => (
              <div className="reorder-row" role="row" key={item.key}>
                <div className="reorder-part">
                  <RiskStatusIcon status={item.status} />
                  <div><strong>{item.name}</strong><span>{item.sku}</span></div>
                </div>
                <div className="reorder-cell reorder-warehouse"><span className="mobile-field-label">Warehouse</span>{item.warehouse}</div>
                <div className="reorder-cell reorder-supplier"><span className="mobile-field-label">Supplier</span>{item.supplier_name || 'Not listed'}</div>
                <div className="reorder-cell numeric"><span className="mobile-field-label">On hand</span>{formatQuantity(item.current_qty)} {item.uom}</div>
                <div className="reorder-cell recommendation-cell"><span className="mobile-field-label">Suggested</span>{item.recommended_qty !== false ? <strong>{formatQuantity(item.recommended_qty)} {item.uom}</strong> : 'Review policy'}</div>
                <div className="reorder-cell"><span className={`alert-stock-status ${item.status === 'out' ? 'out' : item.status === 'shortage' ? 'projected' : 'low'}`}>{item.status_label}</span></div>
                <button type="button" className="review-button" onClick={() => setSelectedKey(item.key)}>Review</button>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <div><span className="empty-icon"><CircleCheck size={19} /></span><strong>{emptyTitle}</strong><p>{emptyCopy}</p></div>
          </div>
        )}
        <div className="coverage-footer">
          {data.coverage.complete
            ? `Reviewed ${formatQuantity(data.coverage.scanned_locations, 0)} product–warehouse positions across ${data.warehouses.length} ${data.warehouses.length === 1 ? 'warehouse' : 'warehouses'}.`
            : `Partial scan: reviewed ${formatQuantity(data.coverage.scanned_locations, 0)} of ${formatQuantity(data.coverage.candidate_locations, 0)} product–warehouse positions.`}
        </div>
      </section>

      <Sheet open={Boolean(selected)} onOpenChange={(open) => { if (!open) setSelectedKey(null) }}>
        <SheetContent side="right" className="recommendation-drawer">
          <SheetHeader>
            <SheetTitle>{selected?.name || 'Restock recommendation'}</SheetTitle>
            <SheetDescription>{selected ? `${selected.sku} · ${selected.warehouse}` : ''}</SheetDescription>
          </SheetHeader>
          {selected && (
            <div className="drawer-content">
              <div className="drawer-summary">
                <span className={`alert-stock-status ${selected.status === 'out' ? 'out' : selected.status === 'shortage' ? 'projected' : 'low'}`}>{selected.status_label}</span>
                <div><span>On hand</span><strong>{formatQuantity(selected.current_qty)} {selected.uom}</strong></div>
                <div><span>Suggested reorder</span><strong>{selected.recommended_qty !== false ? `${formatQuantity(selected.recommended_qty)} ${selected.uom}` : 'Review policy'}</strong></div>
              </div>
              <div className="drawer-section"><span>Supplier</span><strong>{selected.supplier_name || 'Not listed'}</strong></div>
              <div className="drawer-section"><span>Why this needs attention</span><p>{selected.reason}</p></div>
              <div className="drawer-section"><span>How this was calculated</span><p>{selected.basis_note}</p></div>
              <p className="drawer-note">This is planning guidance only. No purchase order is created automatically.</p>
            </div>
          )}
        </SheetContent>
      </Sheet>
    </>
  )
}

export function PanelError({ title, message, onRetry }: { title: string; message: string; onRetry: () => void }) {
  return (
    <section className="panel panel-error" role="alert">
      <span className="panel-error-icon"><RefreshCw size={16} /></span>
      <div><strong>{title}</strong><p>{message}</p></div>
      <button type="button" className="text-retry" onClick={onRetry}>Retry</button>
    </section>
  )
}
