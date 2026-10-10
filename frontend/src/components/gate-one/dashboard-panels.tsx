import { useState, type KeyboardEvent, type PointerEvent } from 'react'
import {
  ArrowRight, BatteryCharging, Boxes, CarFront, Check, ChevronDown, CircleAlert,
  Disc3, Filter, PackageCheck, ShoppingCart, Sparkles, Target, TrendingDown,
  TrendingUp, TriangleAlert, Wind, Zap, type LucideIcon,
} from 'lucide-react'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuRadioGroup, DropdownMenuRadioItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { developmentDashboardFixture as fixture } from '@/data/development-dashboard-fixture'
import {
  forecastFixtures, interactiveProducts, type ForecastFixture, type ForecastHorizon,
  type InteractiveProduct,
} from '@/data/gate-two-fixtures'

const metricIcons: Record<typeof fixture.kpis[number]['icon'], LucideIcon> = {
  boxes: Boxes,
  stock: PackageCheck,
  low: TriangleAlert,
  risk: CircleAlert,
  accuracy: Target,
}

const insightIcons: Record<typeof fixture.insights[number]['icon'], LucideIcon> = {
  trend: TrendingUp,
  reorder: Boxes,
  vehicle: CarFront,
}

const productIcons: Record<InteractiveProduct['icon'], LucideIcon> = {
  brake: Disc3,
  oil: Filter,
  spark: Zap,
  air: Wind,
  battery: BatteryCharging,
}

const metricDetails: Record<string, string> = {
  'Total SKUs': 'The sample catalogue includes every part shown in this local preview.',
  'In Stock': 'Parts with a positive sample quantity available on the shelf.',
  'Low Stock': 'Sample parts approaching their displayed reorder point.',
  'At Risk': 'Sample parts that may need a closer look soon.',
  'Forecast Accuracy': 'An illustrative interface value only; it is not measured business performance.',
}

export function KpiCards() {
  return (
    <section className="kpi-grid" aria-label="Inventory overview">
      {fixture.kpis.map((metric) => {
        const Icon = metricIcons[metric.icon]
        const TrendIcon = metric.trendDirection === 'up' ? TrendingUp : TrendingDown
        return (
          <Tooltip key={metric.label}>
            <TooltipTrigger asChild>
              <article className="kpi-card" tabIndex={0} aria-describedby={`metric-${metric.icon}-detail`}>
                <div className="kpi-card-top">
                  <span className={`kpi-icon kpi-icon-${metric.tone}`}><Icon size={19} strokeWidth={1.9} aria-hidden="true" /></span>
                  <span className="kpi-label">{metric.label}</span>
                  <span className={`kpi-trend kpi-trend-${metric.trendDirection}`}><TrendIcon size={11} strokeWidth={2.3} aria-hidden="true" />{metric.trend}</span>
                </div>
                <strong className="kpi-value">{metric.value}</strong>
                <div className="kpi-note">{metric.note}</div>
                <span className="sr-only" id={`metric-${metric.icon}-detail`}>{metricDetails[metric.label]} Local fixture value: {metric.value}.</span>
              </article>
            </TooltipTrigger>
            <TooltipContent className="business-tooltip" side="bottom">{metricDetails[metric.label]}</TooltipContent>
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
      <span className="legend-key"><i className="legend-band" />Typical range</span>
    </div>
  )
}

type ChartCoordinate = { x: number; y: number }

function smoothPath(points: ChartCoordinate[]) {
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

function coordinate(index: number, value: number, yMaximum: number): ChartCoordinate {
  return { x: index * 100, y: 156 - Math.max(0, Math.min(1, value / yMaximum)) * 152 }
}

function confidencePath(chart: ForecastFixture) {
  const upper = chart.upperRange.map((value, index) => coordinate(index + 4, value, chart.yMaximum))
  const lower = chart.lowerRange.map((value, index) => coordinate(index + 4, value, chart.yMaximum)).reverse()
  return `${upper.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ')} ${lower.map((point) => `L ${point.x} ${point.y}`).join(' ')} Z`
}

function formatUnits(value: number) {
  return new Intl.NumberFormat('en-US').format(value)
}

function ForecastPlot({ product, horizon, chart }: { product: InteractiveProduct; horizon: ForecastHorizon; chart: ForecastFixture }) {
  const [activePoint, setActivePoint] = useState<number | null>(null)
  const xPositions = Array.from({ length: 8 }, (_, index) => index * 100)
  const actualCoordinates = chart.actual.map((value, index) => coordinate(index, value, chart.yMaximum))
  const expectedCoordinates = chart.expected.map((value, index) => coordinate(index + 4, value, chart.yMaximum))
  const currentValue = activePoint !== null && activePoint < 5
    ? chart.actual[activePoint]
    : activePoint !== null ? chart.expected[activePoint - 4] : undefined
  const currentRange = activePoint !== null && activePoint >= 4
    ? { low: chart.lowerRange[activePoint - 4], high: chart.upperRange[activePoint - 4] }
    : null
  const tooltipLeft = activePoint === null ? 50 : Math.max(18, Math.min(82, (activePoint / 7) * 100))

  function selectNearestPoint(event: PointerEvent<HTMLDivElement>) {
    const bounds = event.currentTarget.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width))
    setActivePoint(Math.round(ratio * 7))
  }

  function moveChartPoint(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
    event.preventDefault()
    setActivePoint((index) => Math.max(0, Math.min(7, (index ?? 0) + (event.key === 'ArrowRight' ? 1 : -1))))
  }

  return (
    <div className="forecast-chart" role="group" aria-label={`${product.name}, expected demand over ${horizon} days`}>
      <div className="chart-y-axis" aria-hidden="true">
        {[1, .75, .5, .25, 0].map((part) => <span key={part}>{formatUnits(Math.round(chart.yMaximum * part))}</span>)}
      </div>
      <div className="chart-plot-stack">
        <div
          className="chart-plot chart-plot-interactive"
          tabIndex={0}
          role="group"
          aria-roledescription="interactive chart"
          aria-label="Demand chart. Use the left and right arrow keys to inspect sample points."
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
            {xPositions.map((x) => <line key={`v-${x}`} x1={x} x2={x} y1="4" y2="156" className="chart-grid-line chart-grid-vertical" />)}
            <path d={confidencePath(chart)} fill="url(#forecast-confidence)" />
            <line x1="400" x2="400" y1="4" y2="156" className="forecast-cutoff" />
            <path d={smoothPath(actualCoordinates)} className="history-line" />
            <path d={smoothPath(expectedCoordinates)} className="forecast-line" />
            {actualCoordinates.map((point, index) => <circle key={`actual-${index}`} cx={point.x} cy={point.y} r={index === 4 ? 4.5 : 3.2} className="history-dot" />)}
            {expectedCoordinates.slice(1).map((point, index) => <circle key={`forecast-${index}`} cx={point.x} cy={point.y} r="3.4" className="forecast-dot" />)}
            {activePoint !== null && <line x1={activePoint * 100} x2={activePoint * 100} y1="4" y2="156" className="chart-active-guide" />}
          </svg>
          <div className="chart-pointer-target" aria-hidden="true" />
          <div className="chart-tooltip" data-visible={activePoint !== null} style={{ left: `${tooltipLeft}%` }} role="status" aria-live="polite">
            {activePoint !== null && currentValue !== undefined && <>
              <small>{chart.xLabels[activePoint]}</small>
              <strong><i />{activePoint < 4 ? 'Past demand' : 'Expected demand'}: {formatUnits(currentValue)} units</strong>
              {currentRange && <span>Typical range: {formatUnits(currentRange.low)}–{formatUnits(currentRange.high)}</span>}
            </>}
          </div>
        </div>
        <div className="chart-x-axis" aria-hidden="true">{chart.xLabels.map((label) => <span key={label}>{label}</span>)}</div>
      </div>
    </div>
  )
}

function ChevronDownIcon() {
  return <ChevronDown className="tiny-chevron" aria-hidden="true" />
}

export type DashboardFixtureState = 'ready' | 'loading' | 'empty' | 'error'

export function ForecastCard({
  productSku,
  horizon,
  onProductChange,
  onHorizonChange,
  fixtureState,
  onRetry,
}: {
  productSku: string
  horizon: ForecastHorizon
  onProductChange: (sku: string) => void
  onHorizonChange: (horizon: ForecastHorizon) => void
  fixtureState: DashboardFixtureState
  onRetry: () => void
}) {
  const product = interactiveProducts.find((item) => item.sku === productSku) ?? interactiveProducts[0]
  const chart = forecastFixtures[product.sku]?.[horizon] ?? forecastFixtures['BP-001'][30]
  const yLabels = [chart.yMaximum, chart.yMaximum * .75, chart.yMaximum * .5, chart.yMaximum * .25, 0]

  return (
    <section className="panel forecast-card" aria-labelledby="forecast-title" id="forecast-panel">
      <div className="panel-heading forecast-heading">
        <div className="panel-heading-copy">
          <div className="panel-title-row"><Sparkles className="panel-title-icon" size={19} aria-hidden="true" /><h2 id="forecast-title">Demand forecast</h2></div>
          <p>See what customers may need over the next {horizon} days.</p>
        </div>
        <div className="forecast-controls">
          <label className="select-visual product-select">
            <CarFront size={16} aria-hidden="true" />
            <span className="product-select-name">{product.name}</span>
            <select value={product.sku} aria-label="Forecast product" onChange={(event) => onProductChange(event.currentTarget.value)}>
              {interactiveProducts.map((item) => <option key={item.sku} value={item.sku}>{item.name} · {item.sku}</option>)}
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
      {fixtureState === 'loading' ? <ChartLoadingState /> : fixtureState === 'empty' ? <ChartEmptyState onRetry={onRetry} /> : fixtureState === 'error' ? <ChartErrorState onRetry={onRetry} /> : (
        <ForecastPlot product={product} horizon={horizon} chart={{ ...chart, yMaximum: chart.yMaximum }} />
      )}
      <span className="sr-only" aria-live="polite">Chart scale: {yLabels.map(formatUnits).join(', ')} units.</span>
    </section>
  )
}

function ChartLoadingState() {
  return <div className="fixture-chart-state" role="status" aria-label="Loading sample forecast"><span className="loading-line loading-line-wide" /><span className="loading-line" /><span className="loading-sparkline" /></div>
}

function ChartEmptyState({ onRetry }: { onRetry: () => void }) {
  return <div className="fixture-chart-state fixture-empty-state"><span className="empty-state-icon"><PackageCheck size={20} /></span><strong>No forecast to show yet</strong><p>Load the sample view to explore expected demand.</p><button className="inline-retry-button" type="button" onClick={onRetry}>Show sample forecast</button></div>
}

function ChartErrorState({ onRetry }: { onRetry: () => void }) {
  return <div className="fixture-chart-state fixture-error-state" role="alert"><strong>This sample forecast is unavailable</strong><p>Try loading the preview again.</p><button className="inline-retry-button" type="button" onClick={onRetry}>Try again</button></div>
}

function HealthDonut() {
  const pieces = fixture.health.segments.map((segment, index) => {
    const gap = .4
    const start = fixture.health.segments.slice(0, index).reduce((total, prior) => total + prior.percent * .988 + gap, 0)
    const end = start + segment.percent * .988
    const gapEnd = index === fixture.health.segments.length - 1 ? 100 : end + gap
    return `var(--health-${segment.color}) ${start}% ${end}%, #fff ${end}% ${gapEnd}%`
  })
  return (
    <div className="health-donut" style={{ background: `conic-gradient(from -90deg, ${pieces.join(', ')})` }} role="img" aria-label="Illustrative inventory health: 73 percent healthy, 18 percent low stock, 9 percent out of stock">
      <div className="health-donut-hole"><strong>{fixture.health.total}</strong><span>Total SKUs</span></div>
    </div>
  )
}

export function InventoryHealthCard({ onShowDetails }: { onShowDetails: () => void }) {
  return (
    <section className="panel health-card" aria-labelledby="health-title" id="inventory-health">
      <div className="health-heading">
        <h2 id="health-title">Inventory Health</h2>
        <button className="text-link health-details-button" type="button" onClick={onShowDetails}>See details <ArrowRight size={14} aria-hidden="true" /></button>
      </div>
      <HealthDonut />
      <ul className="health-legend">
        {fixture.health.segments.map((segment) => (
          <li key={segment.label}>
            <span className="health-name"><i className={`health-dot health-dot-${segment.color}`} />{segment.label}</span>
            <strong>{segment.count}</strong>
            <span className={`health-percent health-percent-${segment.color}`}>{segment.percent}%</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

export type InsightAction = 'review-parts' | 'view-reorder' | 'explore-forecast'

const insightActions: Record<typeof fixture.insights[number]['icon'], InsightAction> = {
  trend: 'review-parts',
  reorder: 'view-reorder',
  vehicle: 'explore-forecast',
}

export function InsightsSection({ onAction, onShowAll }: { onAction: (action: InsightAction) => void; onShowAll: () => void }) {
  return (
    <section className="panel insights-panel" aria-labelledby="insights-title" id="insights-panel">
      <div className="section-heading insights-heading">
        <div className="panel-title-row"><Sparkles className="panel-title-icon" size={19} aria-hidden="true" /><h2 id="insights-title">Insights &amp; Recommendations</h2></div>
        <button className="text-link" type="button" onClick={onShowAll}>See all insights <ArrowRight size={14} aria-hidden="true" /></button>
      </div>
      <div className="insight-grid">
        {fixture.insights.map((insight) => {
          const Icon = insightIcons[insight.icon]
          return (
            <article className="insight-card" key={insight.title}>
              <span className="insight-icon"><Icon size={22} strokeWidth={1.8} aria-hidden="true" /></span>
              <div className="insight-copy"><h3>{insight.title}</h3><p>{insight.description}</p></div>
              <button className="insight-action" type="button" onClick={() => onAction(insightActions[insight.icon])}>{insight.action}<ArrowRight size={13} aria-hidden="true" /></button>
            </article>
          )
        })}
      </div>
    </section>
  )
}

export type RiskFilter = 'All' | 'High' | 'Medium'

function FilterMenu({ value, onChange }: { value: RiskFilter; onChange: (value: RiskFilter) => void }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="table-control" type="button" aria-label={`Risk filter: ${value === 'All' ? 'all priorities' : `${value} priority`}`}><Filter size={13} aria-hidden="true" />Filter<ChevronDownIcon /></button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="table-filter-menu">
        <DropdownMenuLabel>Show priority</DropdownMenuLabel><DropdownMenuSeparator />
        <DropdownMenuRadioGroup value={value} onValueChange={(next) => onChange(next as RiskFilter)}>
          <DropdownMenuRadioItem value="All">All priorities</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="High">High priority</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="Medium">Medium priority</DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function CategoryMenu({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const categories = ['All categories', ...new Set(interactiveProducts.map((product) => product.category))]
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="table-control categories-control" type="button" aria-label={`Category: ${value}`}><span>{value === 'All categories' ? 'Categories' : value}</span><ChevronDownIcon /></button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="table-filter-menu">
        <DropdownMenuLabel>Choose a category</DropdownMenuLabel><DropdownMenuSeparator />
        {categories.map((category) => (
          <DropdownMenuItem key={category} onSelect={() => onChange(category)}>
            <span className="menu-choice-check">{category === value ? <Check size={13} /> : null}</span>{category}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function MobileMoreMenu({ onSeeAll, category, onCategoryChange }: { onSeeAll: () => void; category: string; onCategoryChange: (value: string) => void }) {
  const categories = ['All categories', ...new Set(interactiveProducts.map((product) => product.category))]
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="mobile-more-control" type="button" aria-label="More restock list options">•••</button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="table-filter-menu">
        <DropdownMenuLabel>Part category</DropdownMenuLabel>
        {categories.map((item) => <DropdownMenuItem key={item} onSelect={() => onCategoryChange(item)}><span className="menu-choice-check">{item === category ? <Check size={13} /> : null}</span>{item}</DropdownMenuItem>)}
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={onSeeAll}>See all recommendations</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function ReorderTable({
  products,
  riskFilter,
  categoryFilter,
  onRiskFilterChange,
  onCategoryFilterChange,
  onSeeAll,
  onOpenProduct,
  fixtureState,
  onRetry,
  onClearFilters,
}: {
  products: InteractiveProduct[]
  riskFilter: RiskFilter
  categoryFilter: string
  onRiskFilterChange: (value: RiskFilter) => void
  onCategoryFilterChange: (value: string) => void
  onSeeAll: () => void
  onOpenProduct: (product: InteractiveProduct) => void
  fixtureState: DashboardFixtureState
  onRetry: () => void
  onClearFilters: () => void
}) {
  const items = products

  return (
    <section className="panel reorder-panel" aria-labelledby="reorder-title" id="reorder-panel">
      <div className="section-heading reorder-heading">
        <div className="panel-title-row"><ShoppingCart className="panel-title-icon" size={21} aria-hidden="true" /><h2 id="reorder-title">Restock recommendations</h2></div>
        <div className="reorder-controls">
          <FilterMenu value={riskFilter} onChange={onRiskFilterChange} />
          <CategoryMenu value={categoryFilter} onChange={onCategoryFilterChange} />
          <button className="see-all-control" type="button" onClick={onSeeAll}>See all</button>
          <MobileMoreMenu onSeeAll={onSeeAll} category={categoryFilter} onCategoryChange={onCategoryFilterChange} />
        </div>
      </div>
      {fixtureState === 'loading' ? <TableLoadingState /> : fixtureState === 'error' ? <TableErrorState onRetry={onRetry} /> : fixtureState === 'empty' || items.length === 0 ? <TableEmptyState onClearFilters={onClearFilters} fixtureState={fixtureState} /> : (
        <div className="table-scroll-region">
          <table className="reorder-table">
            <colgroup>
              <col className="column-select" /><col className="column-part" /><col className="column-sku" />
              <col className="column-forecast" /><col className="column-stock" /><col className="column-suggested" />
              <col className="column-confidence" /><col className="column-risk" /><col className="column-action" /><col className="column-more" />
            </colgroup>
            <thead><tr>
              <th className="select-col"><span className="checkbox-visual" aria-hidden="true" /></th>
              <th>Part</th><th>SKU</th><th>Expected demand</th><th>Current stock</th><th>Suggested order</th><th>Confidence</th><th>Risk</th><th>Action</th><th aria-label="More actions" />
            </tr></thead>
            <tbody>
              {items.map((part) => {
                const Icon = productIcons[part.icon]
                return (
                  <tr key={part.sku}>
                    <td className="select-col"><span className="checkbox-visual" aria-hidden="true" /></td>
                    <th scope="row" className="part-cell">
                      <span className={`part-thumbnail part-thumbnail-${part.icon}`}><Icon size={24} strokeWidth={1.6} aria-hidden="true" /></span>
                      <button className="part-name" type="button" onClick={() => onOpenProduct(part)} aria-label={`Open ${part.name}, SKU ${part.sku}`}>
                        {part.name}<small className="mobile-sku">{part.sku}</small>
                      </button>
                    </th>
                    <td className="sku-cell">{part.sku}</td>
                    <td className="number-cell"><strong>{part.forecast}</strong><span className="growth-pill"><TrendingUp size={11} aria-hidden="true" />{part.growth}</span></td>
                    <td className="stock-cell">{part.stock}</td>
                    <td className="suggested-cell">{part.suggested}</td>
                    <td className="confidence-cell"><span className="confidence-value">{part.confidence}</span><span className="confidence-track"><i style={{ width: part.confidence }} /></span></td>
                    <td><span className={`risk-pill risk-${part.risk.toLowerCase()}`}>{part.risk}</span></td>
                    <td className="action-cell"><button className="purchase-action" type="button" disabled title="Purchasing is not enabled in this preview">Create PO</button></td>
                    <td className="more-cell"><button className="row-more-button" type="button" aria-label={`Open restock details for ${part.name}`} onClick={() => onOpenProduct(part)}>···</button></td>
                    <td className="mobile-detail">
                      <span><small>Expected</small><strong>{part.forecast} <i>{part.growth}</i></strong></span>
                      <span><small>Current</small><strong>{part.stock}</strong></span>
                      <span><small>Suggested</small><strong>{part.suggested}</strong></span>
                      <button className={`risk-pill risk-${part.risk.toLowerCase()}`} type="button" onClick={() => onOpenProduct(part)} aria-label={`Open ${part.risk.toLowerCase()} priority details for ${part.name}`}>{part.risk} risk</button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="fixture-footnote">Illustrative interface values · not connected to business records</p>
    </section>
  )
}

function TableLoadingState() {
  return <div className="table-state table-loading-state" role="status" aria-label="Loading sample reorder recommendations">{Array.from({ length: 4 }, (_, index) => <span className="loading-table-row" key={index} />)}</div>
}

function TableEmptyState({ onClearFilters, fixtureState }: { onClearFilters: () => void; fixtureState: DashboardFixtureState }) {
  return (
    <div className="table-state fixture-empty-state">
      <span className="empty-state-icon"><Boxes size={19} aria-hidden="true" /></span>
      <strong>{fixtureState === 'empty' ? 'No recommendations to show yet' : 'No parts match these filters'}</strong>
      <p>{fixtureState === 'empty' ? 'There are no sample suggestions in this preview state.' : 'Try another category or clear the filters to see the sample list.'}</p>
      <button className="inline-retry-button" type="button" onClick={onClearFilters}>Show all sample parts</button>
    </div>
  )
}

function TableErrorState({ onRetry }: { onRetry: () => void }) {
  return <div className="table-state fixture-error-state" role="alert"><strong>The sample list is temporarily unavailable</strong><p>Try again to return to the local preview.</p><button className="inline-retry-button" type="button" onClick={onRetry}>Try again</button></div>
}
