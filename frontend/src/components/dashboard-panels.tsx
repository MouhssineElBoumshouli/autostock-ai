import { lazy, Suspense } from 'react'
import {
  AlertTriangle, Boxes, CircleCheck, PackageCheck, PackageMinus, PackageSearch, RefreshCw,
} from 'lucide-react'
import type { DashboardData, ForecastData, RestockData } from '@/api/contracts'
import { combineDemandHistory, formatQuantity } from '@/lib/dashboard'

const HEALTH_COLORS: Record<string, string> = { healthy: '#36a17b', low: '#dfa841', out: '#d56a74' }
const ForecastPlot = lazy(() => import('@/components/charts/forecast-plot'))
const InventoryHealthChart = lazy(() => import('@/components/charts/inventory-health-chart'))

export function KpiGrid({ data }: { data: DashboardData }) {
  const assessmentNote = data.inventory_health.complete
    ? 'Across tracked parts'
    : `Assessment sample of ${formatQuantity(data.inventory_health.sampled_products)} parts`
  const cards = [
    { label: 'Tracked parts', value: data.kpis.tracked_products, note: 'Active parts in this company', color: 'violet', icon: Boxes },
    { label: 'In stock', value: data.kpis.in_stock, note: assessmentNote, color: 'green', icon: PackageCheck },
    { label: 'Low stock', value: data.kpis.low_stock, note: assessmentNote, color: 'amber', icon: PackageSearch },
    { label: 'Out of stock', value: data.kpis.out_of_stock, note: assessmentNote, color: 'red', icon: PackageMinus },
  ]

  return (
    <section className="kpi-grid" aria-label="Inventory summary">
      {cards.map(({ label, value, note, color, icon: Icon }) => (
        <article className="kpi-card" key={label}>
          <div className="kpi-top"><span className="kpi-label">{label}</span><span className={`kpi-icon ${color}`}><Icon size={16} strokeWidth={1.9} /></span></div>
          <div className="kpi-value">{formatQuantity(value, 0)}</div>
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

export function ForecastPanel({ forecast }: { forecast: ForecastData }) {
  if (forecast.status !== 'available') {
    return (
      <section className="panel forecast-panel" aria-labelledby="forecast-title">
        <div className="panel-header">
          <div className="panel-heading"><h2 id="forecast-title" className="panel-title">Demand outlook</h2><p className="panel-subtitle">Recent demand with a short-term projection</p></div>
          <span className="source-pill">Demand forecast</span>
        </div>
        <ChartUnavailable title="Forecast not available" message={forecast.message} />
      </section>
    )
  }

  const run = forecast.forecast
  const chartData = combineDemandHistory(run)
  return (
    <section className="panel forecast-panel" aria-labelledby="forecast-title">
      <div className="panel-header">
        <div className="panel-heading">
          <h2 id="forecast-title" className="panel-title">Demand outlook</h2>
          <p className="panel-subtitle">{run.product_name} <span aria-hidden="true">·</span> {run.warehouse_name || 'Company-wide history'} <span aria-hidden="true">·</span> 60-day history + {run.horizon_days}-day outlook</p>
        </div>
          <span className="source-pill" title={run.source_label}>{run.source_type === 'synthetic_demo' ? 'Demo history' : 'Completed deliveries'}</span>
      </div>
      {chartData.length ? (
        <div className="chart-area" role="img" aria-label={`Daily units for ${run.product_name}; observed delivery history followed by a forecast with an uncertainty range.`}>
          <Suspense fallback={<div className="chart-loading" role="status">Preparing demand chart…</div>}>
            <ForecastPlot data={chartData} uom={run.uom} />
          </Suspense>
        </div>
      ) : <ChartUnavailable title="No dated points to display" message="This saved forecast has no history or projection points for the selected window." />}
      <div className="chart-legend" aria-label="Chart key">
        <span className="legend-item"><span className="legend-line actual" /> Delivered</span>
        <span className="legend-item"><span className="legend-line" /> Forecast</span>
        <span className="legend-item"><span className="legend-band" /> Uncertainty range</span>
      </div>
      <p className="forecast-context">{run.review_status === 'reviewed' ? 'Reviewed forecast' : 'Saved forecast'} · {run.source_label}. Estimates are planning guidance and may not reflect stockout-censored demand.</p>
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
        <div className="panel-heading"><h2 id="health-title" className="panel-title">Inventory health</h2><p className="panel-subtitle">On-hand quantities against safety stock</p></div>
      </div>
      <div className="health-body">
        <div className={`health-chart-wrap ${assessed ? '' : 'health-chart-empty'}`} role="img" aria-label={`${formatQuantity(assessed, 0)} assessed parts: ${categories.map((item) => `${item.count} ${item.label.toLowerCase()}`).join(', ')}`}>
          {assessed > 0 && (
            <Suspense fallback={<div className="health-chart-loading" role="status">Loading chart…</div>}>
              <InventoryHealthChart categories={nonEmpty} colors={HEALTH_COLORS} />
            </Suspense>
          )}
          <div className="health-center"><strong>{formatQuantity(assessed, 0)}</strong><span>assessed</span></div>
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
        {data.inventory_health.complete && data.inventory_health.total_tracked === 0 && (
          <p className="coverage-note neutral-note" role="note">No stockable parts are enabled for AutoStock monitoring in this company.</p>
        )}
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
  const emptyTitle = data.coverage.complete ? 'No priority stock alerts' : 'No priority alerts found in this scan'
  const emptyCopy = data.coverage.complete
    ? 'No current inventory positions are flagged for reorder review.'
    : 'The reviewed portion has no priority items. The remaining catalog still needs a scan.'

  return (
    <section className="panel restock-panel" aria-labelledby="restock-title">
      <div className="panel-header restock-header">
        <div className="panel-heading">
          <div className="restock-heading-wrap"><h2 id="restock-title" className="panel-title">Priority restock</h2><span className="restock-count" aria-label={`${data.items.length} alert${data.items.length === 1 ? '' : 's'}`}>{data.items.length}</span></div>
          <p className="panel-subtitle">Read-only guidance from current Odoo stock and reorder policies</p>
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
        <div className="alert-list">
          {data.items.map((item) => (
            <article className="alert-item" key={item.key}>
              <div className="alert-product">
                <RiskStatusIcon status={item.status} />
                <div className="alert-product-copy">
                  <div className="alert-product-name" title={item.name}>{item.name}</div>
                  <div className="alert-product-sku">{item.sku} <span aria-hidden="true">·</span> {item.status_label}</div>
                  <div className="alert-mobile-current">On hand {formatQuantity(item.current_qty)} {item.uom}</div>
                  <div className="alert-mobile-supplier">Supplier · {item.supplier_name || 'Not listed'}</div>
                </div>
              </div>
              <div className="alert-meta alert-current"><div className="alert-meta-label">On hand</div><div className="alert-meta-value">{formatQuantity(item.current_qty)} {item.uom}</div></div>
              <div className="alert-meta alert-location"><div className="alert-meta-label">Warehouse</div><div className="alert-meta-value" title={item.warehouse}>{item.warehouse}</div></div>
              <div className="alert-meta alert-supplier"><div className="alert-meta-label">Supplier</div><div className="alert-meta-value" title={item.supplier_name || undefined}>{item.supplier_name || 'Supplier not listed'}</div></div>
              <div className="alert-recommendation">
                {item.recommended_qty !== false
                  ? <span className="quantity-pill">{formatQuantity(item.recommended_qty)} <small>{item.uom} suggested</small></span>
                  : <span className="review-policy">Review policy</span>}
                <div className="alert-reason" title={item.basis_note}>{item.reason}</div>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <div><span className="empty-icon"><CircleCheck size={19} /></span><strong>{emptyTitle}</strong><p>{emptyCopy}</p></div>
        </div>
      )}
      {!data.coverage.complete && (
        <div className="coverage-footer" role="note">
          Partial scan: reviewed {formatQuantity(data.coverage.scanned_locations, 0)} of {formatQuantity(data.coverage.candidate_locations, 0)} product–warehouse positions. This preview may omit additional items.
        </div>
      )}
      {data.coverage.complete && (
        <div className="coverage-footer">Reviewed {formatQuantity(data.coverage.scanned_locations, 0)} product–warehouse positions across {data.warehouses.length} {data.warehouses.length === 1 ? 'warehouse' : 'warehouses'}.</div>
      )}
    </section>
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
