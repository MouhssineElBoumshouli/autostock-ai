import { useState, type KeyboardEvent, type PointerEvent } from 'react'
import {
  ArrowRight, BatteryCharging, Boxes, CarFront, Check, ChevronDown, CircleAlert,
  Disc3, Filter, Info, PackageCheck, ShoppingCart, Sparkles, Target,
  TrendingUp, TriangleAlert, Wind, Zap, type LucideIcon,
} from 'lucide-react'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuRadioGroup, DropdownMenuRadioItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import type { DashboardData, DashboardInsight, ForecastData, RestockData, RiskItem } from '@/api/contracts'

export type DashboardPanelState = 'ready' | 'loading' | 'error'
export type ForecastHorizon = 7 | 30 | 60
export type ForecastOption = ForecastData['options'][number]
export type RiskFilter = 'All' | 'High' | 'Medium' | 'Review'
export type DashboardMetric = {
  label: string
  value: string
  note: string
  tone: 'violet' | 'green' | 'amber' | 'red'
  icon: 'boxes' | 'stock' | 'low' | 'risk' | 'review'
  detail: string
}

const metricIcons: Record<DashboardMetric['icon'], LucideIcon> = {
  boxes: Boxes,
  stock: PackageCheck,
  low: TriangleAlert,
  risk: CircleAlert,
  review: Target,
}

const insightIcons: Record<DashboardInsight['icon'], LucideIcon> = {
  trend: TrendingUp,
  reorder: Boxes,
  vehicle: CarFront,
}

type PartIcon = 'brake' | 'oil' | 'spark' | 'air' | 'battery'
const productIcons: Record<PartIcon, LucideIcon> = {
  brake: Disc3,
  oil: Filter,
  spark: Zap,
  air: Wind,
  battery: BatteryCharging,
}

function formatUnits(value: number) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value)
}

function formatCount(value: number) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value)
}

export function KpiCards({ metrics }: { metrics: DashboardMetric[] }) {
  return (
    <section className="kpi-grid" aria-label="Inventory overview">
      {metrics.map((metric) => {
        const Icon = metricIcons[metric.icon]
        return (
          <Tooltip key={metric.label}>
            <TooltipTrigger asChild>
              <article className="kpi-card" tabIndex={0} aria-describedby={`metric-${metric.icon}-detail`}>
                <div className="kpi-card-top">
                  <span className={`kpi-icon kpi-icon-${metric.tone}`}><Icon size={19} strokeWidth={1.9} aria-hidden="true" /></span>
                  <span className="kpi-label">{metric.label}</span>
                  <span className="kpi-trend kpi-trend-current">Current</span>
                </div>
                <strong className="kpi-value">{metric.value}</strong>
                <div className="kpi-note">{metric.note}</div>
                <span className="sr-only" id={`metric-${metric.icon}-detail`}>{metric.detail}</span>
              </article>
            </TooltipTrigger>
            <TooltipContent className="business-tooltip" side="bottom">{metric.detail}</TooltipContent>
          </Tooltip>
        )
      })}
    </section>
  )
}

function ChartLegend() {
  return (
    <div className="chart-legend" aria-label="Chart legend">
      <span className="legend-key"><i className="legend-dot legend-dot-history" />Past demand</span>
      <span className="legend-key"><i className="legend-diamond" />Expected demand</span>
      <span className="legend-key"><i className="legend-band" />Planning range</span>
    </div>
  )
}

type ChartPoint = { x: number; y: number }
type ChartSeries = {
  yMaximum: number
  xLabels: string[]
  actual: number[]
  expected: number[]
  lowerRange: number[]
  upperRange: number[]
}

function smoothPath(points: ChartPoint[]) {
  if (points.length === 0) return ''
  if (points.length === 1) return `M ${points[0].x} ${points[0].y}`
  let path = `M ${points[0].x} ${points[0].y}`
  for (let index = 0; index < points.length - 1; index += 1) {
    const previous = points[Math.max(0, index - 1)]
    const current = points[index]
    const next = points[index + 1]
    const after = points[Math.min(points.length - 1, index + 2)]
    const firstControl = { x: current.x + (next.x - previous.x) / 6, y: current.y + (next.y - previous.y) / 6 }
    const secondControl = { x: next.x - (after.x - current.x) / 6, y: next.y - (after.y - current.y) / 6 }
    path += ` C ${firstControl.x} ${firstControl.y}, ${secondControl.x} ${secondControl.y}, ${next.x} ${next.y}`
  }
  return path
}

function coordinate(x: number, value: number, yMaximum: number): ChartPoint {
  return { x, y: 156 - Math.max(0, Math.min(1, value / yMaximum)) * 152 }
}

function confidencePath(chart: ChartSeries) {
  const positions = chart.upperRange.map((value, index) => coordinate(
    chart.upperRange.length <= 1 ? 400 : 400 + index * (300 / (chart.upperRange.length - 1)),
    value,
    chart.yMaximum,
  ))
  const lower = chart.lowerRange.map((value, index) => coordinate(
    chart.lowerRange.length <= 1 ? 400 : 400 + index * (300 / (chart.lowerRange.length - 1)),
    value,
    chart.yMaximum,
  )).reverse()
  return `${positions.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ')} ${lower.map((point) => `L ${point.x} ${point.y}`).join(' ')} Z`
}

function sampleEvenly<T>(items: T[], count: number): T[] {
  if (items.length <= count) return items
  return Array.from({ length: count }, (_, index) => items[Math.round(index * (items.length - 1) / (count - 1))])
}

function axisDate(date: string) {
  const parsed = new Date(`${date}T12:00:00`)
  return Number.isNaN(parsed.getTime()) ? date : new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(parsed)
}

function forecastChart(forecast: Extract<ForecastData, { status: 'available' }>['forecast']): ChartSeries {
  const actual = sampleEvenly(forecast.history, 4)
  const expected = sampleEvenly(forecast.predictions, 4)
  const upperRange = expected.map((point) => point.upper)
  const lowerRange = expected.map((point) => point.lower)
  return {
    yMaximum: Math.max(1, ...actual.map((point) => point.units), ...upperRange),
    xLabels: [...actual.map((point) => axisDate(point.date)), ...expected.map((point) => axisDate(point.date))],
    actual: actual.map((point) => point.units),
    expected: expected.map((point) => point.units),
    lowerRange,
    upperRange,
  }
}

function ForecastPlot({ name, horizon, unit, chart }: { name: string; horizon: ForecastHorizon; unit: string; chart: ChartSeries }) {
  const [activePoint, setActivePoint] = useState<number | null>(null)
  const actualCoordinates = chart.actual.map((value, index) => coordinate(
    chart.actual.length <= 1 ? 400 : index * (400 / (chart.actual.length - 1)), value, chart.yMaximum,
  ))
  const expectedCoordinates = chart.expected.map((value, index) => coordinate(
    chart.expected.length <= 1 ? 400 : 400 + index * (300 / (chart.expected.length - 1)), value, chart.yMaximum,
  ))
  const points = [
    ...actualCoordinates.map((point, index) => ({ ...point, label: chart.xLabels[index] ?? '', value: chart.actual[index], expected: false as const })),
    ...expectedCoordinates.map((point, index) => ({ ...point, label: chart.xLabels[chart.actual.length + index] ?? '', value: chart.expected[index], expected: true as const, range: { low: chart.lowerRange[index], high: chart.upperRange[index] } })),
  ]
  const current = activePoint === null ? undefined : points[activePoint]
  const tooltipLeft = current ? Math.max(18, Math.min(82, current.x / 7)) : 50

  function selectNearestPoint(event: PointerEvent<HTMLDivElement>) {
    const bounds = event.currentTarget.getBoundingClientRect()
    const position = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width)) * 700
    const closest = points.reduce((best, point, index) => Math.abs(point.x - position) < Math.abs(points[best].x - position) ? index : best, 0)
    setActivePoint(closest)
  }

  function moveChartPoint(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
    event.preventDefault()
    setActivePoint((index) => Math.max(0, Math.min(points.length - 1, (index ?? 0) + (event.key === 'ArrowRight' ? 1 : -1))))
  }

  return (
    <div className="forecast-chart" role="group" aria-label={`${name}, expected demand over ${horizon} days`}>
      <div className="chart-y-axis" aria-hidden="true">
        {[1, .75, .5, .25, 0].map((part) => <span key={part}>{formatUnits(Math.round(chart.yMaximum * part))}</span>)}
      </div>
      <div className="chart-plot-stack">
        <div
          className="chart-plot chart-plot-interactive"
          tabIndex={0}
          role="group"
          aria-roledescription="interactive chart"
          aria-label="Demand chart. Use the left and right arrow keys to inspect points."
          onPointerMove={selectNearestPoint}
          onPointerDown={selectNearestPoint}
          onPointerLeave={() => setActivePoint(null)}
          onFocus={() => setActivePoint((index) => index ?? 0)}
          onBlur={() => setActivePoint(null)}
          onKeyDown={moveChartPoint}
          data-testid="forecast-plot"
        >
          <svg viewBox="0 0 700 160" preserveAspectRatio="none" focusable="false" aria-hidden="true">
            <defs>
              <linearGradient id="forecast-confidence" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0" stopColor="#8864f3" stopOpacity=".19" />
                <stop offset="1" stopColor="#8864f3" stopOpacity=".05" />
              </linearGradient>
            </defs>
            {[4, 42, 80, 118, 156].map((y) => <line key={`h-${y}`} x1="0" x2="700" y1={y} y2={y} className="chart-grid-line" />)}
            {Array.from({ length: 8 }, (_, index) => index * 100).map((x) => <line key={`v-${x}`} x1={x} x2={x} y1="4" y2="156" className="chart-grid-line chart-grid-vertical" />)}
            {chart.upperRange.length > 0 && <path d={confidencePath(chart)} fill="url(#forecast-confidence)" />}
            <line x1="400" x2="400" y1="4" y2="156" className="forecast-cutoff" />
            <path d={smoothPath(actualCoordinates)} className="history-line" />
            <path d={smoothPath(expectedCoordinates)} className="forecast-line" />
            {actualCoordinates.map((point, index) => <circle key={`actual-${index}`} cx={point.x} cy={point.y} r={index === actualCoordinates.length - 1 ? 4.5 : 3.2} className="history-dot" />)}
            {expectedCoordinates.map((point, index) => <circle key={`forecast-${index}`} cx={point.x} cy={point.y} r="3.4" className="forecast-dot" />)}
            {current && <line x1={current.x} x2={current.x} y1="4" y2="156" className="chart-active-guide" />}
          </svg>
          <div className="chart-pointer-target" aria-hidden="true" />
          <div className="chart-tooltip" data-visible={Boolean(current)} style={{ left: `${tooltipLeft}%` }} role="status" aria-live="polite">
            {current && <>
              <small>{current.label}</small>
              <strong><i />{current.expected ? 'Expected demand' : 'Past demand'}: {formatUnits(current.value)} {unit}</strong>
              {current.expected && current.range && <span>Planning range: {formatUnits(current.range.low)}–{formatUnits(current.range.high)} {unit}</span>}
            </>}
          </div>
        </div>
        <div className="chart-x-axis" aria-hidden="true">{chart.xLabels.map((label, index) => <span key={`${label}-${index}`}>{label}</span>)}</div>
      </div>
    </div>
  )
}

function ChevronDownIcon() {
  return <ChevronDown className="tiny-chevron" aria-hidden="true" />
}

export function ForecastCard({
  forecast,
  options,
  selectedKey,
  horizon,
  onProductChange,
  onHorizonChange,
  state,
  onRetry,
}: {
  forecast: ForecastData | undefined
  options: ForecastOption[]
  selectedKey: string | null
  horizon: ForecastHorizon
  onProductChange: (key: string) => void
  onHorizonChange: (horizon: ForecastHorizon) => void
  state: DashboardPanelState
  onRetry: () => void
}) {
  const selected = options.find((item) => item.key === selectedKey) ?? options[0]
  const data = forecast?.status === 'available' ? forecast.forecast : null
  const chart = data ? forecastChart(data) : null
  const yLabels = chart ? [chart.yMaximum, chart.yMaximum * .75, chart.yMaximum * .5, chart.yMaximum * .25, 0] : []
  const unavailableMessage = forecast && forecast.status !== 'available' ? forecast.message : 'No completed delivery forecast is available for this period.'

  return (
    <section className="panel forecast-card" aria-labelledby="forecast-title" id="forecast-panel">
      <div className="panel-heading forecast-heading">
        <div className="panel-heading-copy">
          <div className="panel-title-row"><Sparkles className="panel-title-icon" size={19} aria-hidden="true" /><h2 id="forecast-title">Demand forecast</h2></div>
          <p>{data ? `Based on ${data.source_label.toLowerCase()} · next ${horizon} days.` : `Demand expected over the next ${horizon} days.`}</p>
        </div>
        <div className="forecast-controls">
          <label className="select-visual product-select">
            <CarFront size={16} aria-hidden="true" />
            <span className="product-select-name">{selected ? `${selected.name}${selected.warehouse ? ` · ${selected.warehouse}` : ''}` : 'No saved forecast'}</span>
            <select value={selected?.key ?? ''} aria-label="Forecast product" disabled={!options.length} onChange={(event) => onProductChange(event.currentTarget.value)}>
              {!options.length && <option value="">No saved forecast</option>}
              {options.map((item) => <option key={item.key} value={item.key}>{item.name} · {item.sku}{item.warehouse ? ` · ${item.warehouse}` : ''}</option>)}
            </select>
            <ChevronDownIcon />
          </label>
          <label className="select-visual period-select">
            <span>{horizon} days</span>
            <select value={horizon} aria-label="Forecast horizon" onChange={(event) => onHorizonChange(Number(event.currentTarget.value) as ForecastHorizon)}>
              <option value="7">7 days</option><option value="30">30 days</option><option value="60">60 days</option>
            </select>
            <ChevronDownIcon />
          </label>
        </div>
      </div>
      <ChartLegend />
      {state === 'loading' ? <ChartLoadingState /> : state === 'error' ? <ChartErrorState onRetry={onRetry} /> : chart ? (
        <>
          <ForecastPlot name={data?.product_name ?? selected?.name ?? 'Selected part'} horizon={horizon} unit={data?.uom ?? 'units'} chart={chart} />
          <Tooltip>
            <TooltipTrigger asChild><button className="forecast-info" type="button" aria-label="About this forecast"><Info size={13} aria-hidden="true" />About this forecast</button></TooltipTrigger>
            <TooltipContent className="business-tooltip" side="bottom" align="start">
              <strong>{data?.source_label}</strong><br />{data?.limitations}
            </TooltipContent>
          </Tooltip>
        </>
      ) : <ChartEmptyState message={unavailableMessage} onRetry={onRetry} />}
      {chart && <span className="sr-only" aria-live="polite">Chart scale: {yLabels.map(formatUnits).join(', ')} {data?.uom}.</span>}
    </section>
  )
}

function ChartLoadingState() {
  return <div className="dashboard-chart-state" role="status" aria-label="Loading demand forecast"><span className="loading-line loading-line-wide" /><span className="loading-line" /><span className="loading-sparkline" /></div>
}

function ChartEmptyState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <div className="dashboard-chart-state dashboard-empty-state"><span className="empty-state-icon"><PackageCheck size={20} aria-hidden="true" /></span><strong>No forecast to show yet</strong><p>{message}</p><button className="inline-retry-button" type="button" onClick={onRetry}>Try again</button></div>
}

function ChartErrorState({ onRetry }: { onRetry: () => void }) {
  return <div className="dashboard-chart-state dashboard-error-state" role="alert"><strong>The forecast could not be loaded</strong><p>Check your Odoo connection and try again.</p><button className="inline-retry-button" type="button" onClick={onRetry}>Try again</button></div>
}

const healthColor: Record<DashboardData['inventory_health']['categories'][number]['key'], string> = {
  healthy: 'green',
  low: 'amber',
  out: 'red',
}

function HealthDonut({ health }: { health: DashboardData['inventory_health'] }) {
  const pieces = health.categories.map((segment, index) => {
    const gap = 0.4
    const start = health.categories.slice(0, index).reduce((total, prior) => total + prior.percent * .988 + gap, 0)
    const end = start + segment.percent * .988
    const gapEnd = index === health.categories.length - 1 ? 100 : end + gap
    return `var(--health-${healthColor[segment.key]}) ${start}% ${end}%, #fff ${end}% ${gapEnd}%`
  })
  const summary = health.categories.map((segment) => `${segment.percent}% ${segment.label.toLowerCase()}`).join(', ')
  return (
    <div className="health-donut" style={{ background: `conic-gradient(from -90deg, ${pieces.join(', ')})` }} role="img" aria-label={`Inventory health in the current company summary: ${summary}`}>
      <div className="health-donut-hole"><strong>{formatCount(health.sampled_products)}</strong><span>{health.complete ? 'Tracked parts' : 'Counted parts'}</span></div>
    </div>
  )
}

export function InventoryHealthCard({ health, onShowDetails }: { health: DashboardData['inventory_health']; onShowDetails: () => void }) {
  return (
    <section className="panel health-card" aria-labelledby="health-title" id="inventory-health">
      <div className="health-heading">
        <h2 id="health-title">Inventory Health</h2>
        <button className="text-link health-details-button" type="button" onClick={onShowDetails}>See details <ArrowRight size={14} aria-hidden="true" /></button>
      </div>
      <HealthDonut health={health} />
      <ul className="health-legend">
        {health.categories.map((segment) => (
          <li key={segment.key}>
            <span className="health-name"><i className={`health-dot health-dot-${healthColor[segment.key]}`} />{segment.label}</span>
            <strong>{formatCount(segment.count)}</strong>
            <span className={`health-percent health-percent-${healthColor[segment.key]}`}>{segment.percent}%</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

export type InsightAction = DashboardInsight['action']

export function InsightsSection({ insights, onAction, onShowAll }: { insights: DashboardInsight[]; onAction: (action: InsightAction) => void; onShowAll: () => void }) {
  return (
    <section className="panel insights-panel" aria-labelledby="insights-title" id="insights-panel">
      <div className="section-heading insights-heading">
        <div className="panel-title-row"><Sparkles className="panel-title-icon" size={19} aria-hidden="true" /><h2 id="insights-title">Insights &amp; Recommendations</h2></div>
        <button className="text-link" type="button" onClick={onShowAll}>See all insights <ArrowRight size={14} aria-hidden="true" /></button>
      </div>
      <div className="insight-grid">
        {insights.map((insight) => {
          const Icon = insightIcons[insight.icon]
          return (
            <article className="insight-card" key={insight.id}>
              <span className="insight-icon"><Icon size={22} strokeWidth={1.8} aria-hidden="true" /></span>
              <div className="insight-copy"><h3>{insight.title}</h3><p>{insight.description}</p></div>
              <button className="insight-action" type="button" onClick={() => onAction(insight.action)}>{insight.action_label}<ArrowRight size={13} aria-hidden="true" /></button>
            </article>
          )
        })}
      </div>
    </section>
  )
}

function riskLevel(item: RiskItem): Exclude<RiskFilter, 'All'> {
  if (item.status === 'out' || item.status === 'shortage') return 'High'
  if (item.status === 'low') return 'Medium'
  return 'Review'
}

function riskTableLabel(item: RiskItem) {
  if (item.status === 'out') return 'Out of stock'
  if (item.status === 'shortage') return 'Shortage'
  if (item.status === 'low') return 'At trigger'
  if (item.status === 'policy_missing') return 'Review policy'
  return item.status_label
}

function partIcon(item: RiskItem): PartIcon {
  const text = `${item.category} ${item.name}`.toLowerCase()
  if (/brak|rotor|disc/.test(text)) return 'brake'
  if (/oil|filter|fluid/.test(text)) return 'oil'
  if (/spark|ignition|plug/.test(text)) return 'spark'
  if (/battery|electrical|alternator/.test(text)) return 'battery'
  return 'air'
}

function formatQuantity(value: number | false, uom: string) {
  return value === false ? '—' : `${formatUnits(value)} ${uom}`
}

function FilterMenu({ value, onChange }: { value: RiskFilter; onChange: (value: RiskFilter) => void }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="table-control" type="button" aria-label={`Risk filter: ${value === 'All' ? 'all priorities' : `${value} priority`} `}><Filter size={13} aria-hidden="true" />Filter<ChevronDownIcon /></button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="table-filter-menu">
        <DropdownMenuLabel>Show priority</DropdownMenuLabel><DropdownMenuSeparator />
        <DropdownMenuRadioGroup value={value} onValueChange={(next) => onChange(next as RiskFilter)}>
          <DropdownMenuRadioItem value="All">All priorities</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="High">High priority</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="Medium">Medium priority</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="Review">Review needed</DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function CategoryMenu({ value, categories, onChange }: { value: string; categories: string[]; onChange: (value: string) => void }) {
  const options = ['All categories', ...new Set(categories)]
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="table-control categories-control" type="button" aria-label={`Category: ${value}`}><span>{value === 'All categories' ? 'Categories' : value}</span><ChevronDownIcon /></button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="table-filter-menu">
        <DropdownMenuLabel>Choose a category</DropdownMenuLabel><DropdownMenuSeparator />
        {options.map((category) => (
          <DropdownMenuItem key={category} onSelect={() => onChange(category)}>
            <span className="menu-choice-check">{category === value ? <Check size={13} /> : null}</span>{category}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function MobileMoreMenu({ onSeeAll, categories, category, onCategoryChange }: { onSeeAll: () => void; categories: string[]; category: string; onCategoryChange: (value: string) => void }) {
  const options = ['All categories', ...new Set(categories)]
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="mobile-more-control" type="button" aria-label="More restock list options">•••</button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="table-filter-menu">
        <DropdownMenuLabel>Part category</DropdownMenuLabel>
        {options.map((item) => <DropdownMenuItem key={item} onSelect={() => onCategoryChange(item)}><span className="menu-choice-check">{item === category ? <Check size={13} /> : null}</span>{item}</DropdownMenuItem>)}
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={onSeeAll}>View top 5</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function ReorderTable({
  products,
  riskFilter,
  categoryFilter,
  coverage,
  onRiskFilterChange,
  onCategoryFilterChange,
  onSeeAll,
  onOpenProduct,
  state,
  errorMessage,
  onRetry,
  onClearFilters,
}: {
  products: RiskItem[]
  riskFilter: RiskFilter
  categoryFilter: string
  coverage: RestockData['coverage']
  onRiskFilterChange: (value: RiskFilter) => void
  onCategoryFilterChange: (value: string) => void
  onSeeAll: () => void
  onOpenProduct: (product: RiskItem) => void
  state: DashboardPanelState
  errorMessage: string
  onRetry: () => void
  onClearFilters: () => void
}) {
  const categories = products.map((product) => product.category)
  const items = products.filter((product) => (
    (riskFilter === 'All' || riskLevel(product) === riskFilter)
    && (categoryFilter === 'All categories' || product.category === categoryFilter)
  ))
  const hasFilters = riskFilter !== 'All' || categoryFilter !== 'All categories'
  const coverageNote = coverage.complete
    ? `Read-only guidance · scanned ${formatCount(coverage.scanned_locations)} stock positions.`
    : `Partial scan · ${formatCount(coverage.scanned_locations)} of ${formatCount(coverage.candidate_locations)} stock positions checked; more may need review.`

  return (
    <section className="panel reorder-panel" aria-labelledby="reorder-title" id="reorder-panel">
      <div className="section-heading reorder-heading">
        <div className="panel-title-row"><ShoppingCart className="panel-title-icon" size={21} aria-hidden="true" /><h2 id="reorder-title">Restock recommendations</h2></div>
        <div className="reorder-controls">
          <FilterMenu value={riskFilter} onChange={onRiskFilterChange} />
          <CategoryMenu value={categoryFilter} categories={categories} onChange={onCategoryFilterChange} />
          <button className="see-all-control" type="button" onClick={onSeeAll}>View top 5</button>
          <MobileMoreMenu onSeeAll={onSeeAll} categories={categories} category={categoryFilter} onCategoryChange={onCategoryFilterChange} />
        </div>
      </div>
      {state === 'loading' ? <TableLoadingState /> : state === 'error' ? <TableErrorState message={errorMessage} onRetry={onRetry} /> : items.length === 0 ? <TableEmptyState hasFilters={hasFilters} onClearFilters={onClearFilters} /> : (
        <div className="table-scroll-region">
          <table className="reorder-table">
            <colgroup>
              <col className="column-select" /><col className="column-part" /><col className="column-sku" />
              <col className="column-forecast" /><col className="column-stock" /><col className="column-suggested" />
              <col className="column-confidence" /><col className="column-risk" /><col className="column-action" /><col className="column-more" />
            </colgroup>
            <thead><tr>
              <th className="select-col"><span className="checkbox-visual" aria-hidden="true" /></th>
              <th>Part</th><th>SKU</th><th>Demand to delivery</th><th>Current stock</th><th>Suggested order</th><th>Data basis</th><th>Risk</th><th>Review</th><th aria-label="More details" />
            </tr></thead>
            <tbody>
              {items.map((part) => {
                const Icon = productIcons[partIcon(part)]
                const level = riskLevel(part)
                return (
                  <tr key={part.key}>
                    <td className="select-col"><span className="checkbox-visual" aria-hidden="true" /></td>
                    <th scope="row" className="part-cell">
                      <span className={`part-thumbnail part-thumbnail-${partIcon(part)}`}><Icon size={24} strokeWidth={1.6} aria-hidden="true" /></span>
                      <button className="part-name" type="button" onClick={() => onOpenProduct(part)} aria-label={`Open ${part.name}, SKU ${part.sku}`}>
                        {part.name}<small className="mobile-sku">{part.sku}</small>
                      </button>
                    </th>
                    <td className="sku-cell">{part.sku}</td>
                    <td className="number-cell"><strong>{part.forecast_used ? formatUnits(Number(part.forecast_demand)) : '—'}</strong><span className="growth-pill" title={part.forecast_used ? 'Reviewed delivery forecast is included in the Odoo recommendation.' : part.forecast_reason || 'No eligible reviewed forecast was available.'}>{part.forecast_used ? 'Reviewed demand' : 'Not available'}</span></td>
                    <td className="stock-cell">{formatQuantity(part.current_qty, part.uom)}</td>
                    <td className="suggested-cell">{formatQuantity(part.recommended_qty, part.uom)}</td>
                    <td className="confidence-cell"><span className="confidence-value">{part.forecast_used ? 'Stock + demand' : 'Stock + policy'}</span></td>
                    <td><span className={`risk-pill risk-${level.toLowerCase()}`} title={part.status_label}>{riskTableLabel(part)}</span></td>
                    <td className="action-cell"><button className="purchase-action" type="button" onClick={() => onOpenProduct(part)}>Review</button></td>
                    <td className="more-cell"><button className="row-more-button" type="button" aria-label={`Open restock details for ${part.name}`} onClick={() => onOpenProduct(part)}>···</button></td>
                    <td className="mobile-detail">
                      <span><small>Demand to delivery</small><strong>{part.forecast_used ? `${formatUnits(Number(part.forecast_demand))} ${part.uom}` : 'Not available'}</strong></span>
                      <span><small>Current</small><strong>{formatQuantity(part.current_qty, part.uom)}</strong></span>
                      <span><small>Suggested</small><strong>{formatQuantity(part.recommended_qty, part.uom)}</strong></span>
                      <button className={`risk-pill risk-${level.toLowerCase()}`} type="button" onClick={() => onOpenProduct(part)} aria-label={`Open ${part.status_label} details for ${part.name}`}>{riskTableLabel(part)}</button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="coverage-footnote">{coverageNote} Purchasing is read-only.</p>
    </section>
  )
}

function TableLoadingState() {
  return <div className="table-state table-loading-state" role="status" aria-label="Loading restock recommendations">{Array.from({ length: 4 }, (_, index) => <span className="loading-table-row" key={index} />)}</div>
}

function TableEmptyState({ hasFilters, onClearFilters }: { hasFilters: boolean; onClearFilters: () => void }) {
  return (
    <div className="table-state dashboard-empty-state">
      <span className="empty-state-icon"><Boxes size={19} aria-hidden="true" /></span>
      <strong>{hasFilters ? 'No parts match these filters' : 'No stock positions need review'}</strong>
      <p>{hasFilters ? 'Try another category or priority, or clear the filters.' : 'No current stock positions meet the configured review conditions.'}</p>
      {hasFilters && <button className="inline-retry-button" type="button" onClick={onClearFilters}>Clear filters</button>}
    </div>
  )
}

function TableErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <div className="table-state dashboard-error-state" role="alert"><strong>Restock recommendations could not be loaded</strong><p>{message}</p><button className="inline-retry-button" type="button" onClick={onRetry}>Try again</button></div>
}
