import {
  ArrowRight, BatteryCharging, Boxes, CarFront, CircleAlert, Disc3, Filter, PackageCheck,
  ShoppingCart, Sparkles,
  Target, TrendingDown, TrendingUp, TriangleAlert, Wind, Zap, type LucideIcon,
} from 'lucide-react'
import { developmentDashboardFixture as fixture } from '@/data/development-dashboard-fixture'

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

const productIcons: Record<typeof fixture.reorder[number]['icon'], LucideIcon> = {
  brake: Disc3,
  oil: Filter,
  spark: Zap,
  air: Wind,
  battery: BatteryCharging,
}

export function KpiCards() {
  return (
    <section className="kpi-grid" aria-label="Inventory overview">
      {fixture.kpis.map((metric) => {
        const Icon = metricIcons[metric.icon]
        const TrendIcon = metric.trendDirection === 'up' ? TrendingUp : TrendingDown
        return (
          <article className="kpi-card" key={metric.label}>
            <div className="kpi-card-top">
              <span className={`kpi-icon kpi-icon-${metric.tone}`}><Icon size={19} strokeWidth={1.9} aria-hidden="true" /></span>
            <span className="kpi-label">{metric.label}</span>
              <span className={`kpi-trend kpi-trend-${metric.trendDirection}`}><TrendIcon size={11} strokeWidth={2.3} aria-hidden="true" />{metric.trend}</span>
            </div>
            <strong className="kpi-value">{metric.value}</strong>
            <div className="kpi-note">{metric.note}</div>
          </article>
        )
      })}
    </section>
  )
}

function ChartLegend() {
  return (
    <div className="chart-legend" aria-label="Chart legend">
      <span className="legend-key"><i className="legend-dot legend-dot-history" />Historical Demand</span>
      <span className="legend-key"><i className="legend-diamond" />AI Forecast</span>
      <span className="legend-key"><i className="legend-band" />Confidence Range</span>
    </div>
  )
}

function ForecastPlot() {
  const chart = fixture.forecast
  return (
    <div className="forecast-chart" role="img" aria-label="Illustrative weekly brake pad demand chart showing historical demand and a rising forecast with a confidence range">
      <div className="chart-y-axis" aria-hidden="true">
        {chart.yLabels.map((label) => <span key={label}>{label}</span>)}
      </div>
      <div className="chart-plot-stack">
        <div className="chart-plot">
          <svg viewBox="0 0 700 160" preserveAspectRatio="none" focusable="false" aria-hidden="true">
            <defs>
              <linearGradient id="forecast-confidence" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0" stopColor="#8864f3" stopOpacity=".19" />
                <stop offset="1" stopColor="#8864f3" stopOpacity=".05" />
              </linearGradient>
            </defs>
            {[4, 42, 80, 118, 156].map((y) => <line key={`h-${y}`} x1="0" x2="700" y1={y} y2={y} className="chart-grid-line" />)}
            {[0, 100, 200, 300, 400, 500, 600, 700].map((x) => <line key={`v-${x}`} x1={x} x2={x} y1="4" y2="156" className="chart-grid-line chart-grid-vertical" />)}
            <path d={chart.confidencePath} fill="url(#forecast-confidence)" />
            <line x1={chart.forecastStartX} x2={chart.forecastStartX} y1="4" y2="156" className="forecast-cutoff" />
            <path d={chart.historyPath} className="history-line" />
            <path d={chart.forecastPath} className="forecast-line" />
            {chart.historyDots.map((dot, index) => <circle key={index} cx={dot.x} cy={dot.y} r={index === 8 ? 4.5 : 3.2} className="history-dot" />)}
            <circle cx={chart.forecastStartX} cy="118" r="4.2" className="forecast-dot" />
          </svg>
            <div className="chart-tooltip" aria-hidden="true"><small>Feb 12, 2025</small><strong><i />Demand: 720 units</strong></div>
        </div>
        <div className="chart-x-axis" aria-hidden="true">
          {chart.xLabels.map((label) => <span key={label}>{label}</span>)}
        </div>
      </div>
    </div>
  )
}

export function ForecastCard() {
  return (
    <section className="panel forecast-card" aria-labelledby="forecast-title">
      <div className="panel-heading forecast-heading">
        <div className="panel-heading-copy">
          <div className="panel-title-row"><Sparkles className="panel-title-icon" size={19} aria-hidden="true" /><h2 id="forecast-title">AI Demand Forecast</h2></div>
          <p>Predicted demand for key automotive parts (next 12 weeks)</p>
        </div>
        <div className="forecast-controls" aria-hidden="true">
          <span className="select-visual product-select"><CarFront size={16} /><span className="product-select-name">Brake Pads</span><ChevronDownIcon /></span>
          <span className="select-visual period-select">12 Weeks<ChevronDownIcon /></span>
        </div>
      </div>
      <ChartLegend />
      <ForecastPlot />
    </section>
  )
}

function ChevronDownIcon() {
  return <svg className="tiny-chevron" viewBox="0 0 12 12" aria-hidden="true"><path d="m3 4.5 3 3 3-3" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" /></svg>
}

function HealthDonut() {
  const pieces = fixture.health.segments.map((segment, index) => {
    const gap = .4
    const start = fixture.health.segments
      .slice(0, index)
      .reduce((total, prior) => total + prior.percent * .988 + gap, 0)
    const end = start + segment.percent * .988
    const gapEnd = index === fixture.health.segments.length - 1 ? 100 : end + gap
    return `var(--health-${segment.color}) ${start}% ${end}%, #fff ${end}% ${gapEnd}%`
  })
  const style = { background: `conic-gradient(from -90deg, ${pieces.join(', ')})` }
  return (
    <div className="health-donut" style={style} role="img" aria-label="Illustrative inventory health: 73 percent healthy, 18 percent low stock, 9 percent out of stock">
      <div className="health-donut-hole"><strong>{fixture.health.total}</strong><span>Total SKUs</span></div>
    </div>
  )
}

export function InventoryHealthCard() {
  return (
    <section className="panel health-card" aria-labelledby="health-title">
      <div className="health-heading">
        <h2 id="health-title">Inventory Health</h2>
        <span className="text-link" aria-hidden="true">See Details <ArrowRight size={14} /></span>
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

export function InsightsSection() {
  return (
    <section className="panel insights-panel" aria-labelledby="insights-title">
      <div className="section-heading insights-heading">
        <div className="panel-title-row"><Sparkles className="panel-title-icon" size={19} aria-hidden="true" /><h2 id="insights-title">AI Insights &amp; Recommendations</h2></div>
        <span className="text-link" aria-hidden="true">See All Insights <ArrowRight size={14} /></span>
      </div>
      <div className="insight-grid">
        {fixture.insights.map((insight) => {
          const Icon = insightIcons[insight.icon]
          return (
            <article className="insight-card" key={insight.title}>
              <span className="insight-icon"><Icon size={22} strokeWidth={1.8} aria-hidden="true" /></span>
              <div className="insight-copy"><h3>{insight.title}</h3><p>{insight.description}</p></div>
              <span className="insight-action" aria-hidden="true">{insight.action}<ArrowRight size={13} /></span>
            </article>
          )
        })}
      </div>
    </section>
  )
}

export function ReorderTable() {
  return (
    <section className="panel reorder-panel" aria-labelledby="reorder-title">
      <div className="section-heading reorder-heading">
        <div className="panel-title-row"><ShoppingCart className="panel-title-icon" size={21} aria-hidden="true" /><h2 id="reorder-title">Predicted Reorder Recommendations</h2></div>
        <div className="reorder-controls" aria-hidden="true">
          <span className="table-control"><Filter size={13} />Filter<ChevronDownIcon /></span>
          <span className="table-control categories-control">Categories<ChevronDownIcon /></span>
          <span className="see-all-control">See All</span>
        </div>
      </div>
      <div className="table-scroll-region">
        <table className="reorder-table">
          <colgroup>
            <col className="column-select" /><col className="column-part" /><col className="column-sku" />
            <col className="column-forecast" /><col className="column-stock" /><col className="column-suggested" />
            <col className="column-confidence" /><col className="column-risk" /><col className="column-action" /><col className="column-more" />
          </colgroup>
          <thead><tr>
            <th className="select-col"><span className="checkbox-visual" aria-hidden="true" /></th>
            <th>Part</th><th>SKU</th><th>Forecast (30d)</th><th>Current Stock</th><th>Suggested Order</th><th>Confidence</th><th>Risk</th><th>Action</th><th aria-label="More actions" />
          </tr></thead>
          <tbody>
            {fixture.reorder.map((part) => {
              const Icon = productIcons[part.icon]
              return (
                <tr key={part.sku}>
                  <td className="select-col"><span className="checkbox-visual" aria-hidden="true" /></td>
                  <th scope="row" className="part-cell">
                    <span className={`part-thumbnail part-thumbnail-${part.icon}`}><Icon size={24} strokeWidth={1.6} aria-hidden="true" /></span>
                    <span className="part-name">{part.name}<small className="mobile-sku">{part.sku}</small></span>
                  </th>
                  <td className="sku-cell">{part.sku}</td>
                  <td className="number-cell"><strong>{part.forecast}</strong><span className="growth-pill"><TrendingUp size={11} />{part.growth}</span></td>
                  <td className="stock-cell">{part.stock}</td>
                  <td className="suggested-cell">{part.suggested}</td>
                  <td className="confidence-cell"><span className="confidence-value">{part.confidence}</span><span className="confidence-track"><i style={{ width: part.confidence }} /></span></td>
                  <td><span className={`risk-pill risk-${part.risk.toLowerCase()}`}>{part.risk}</span></td>
                  <td className="action-cell"><span className="purchase-action" aria-hidden="true">Create PO</span></td>
                  <td className="more-cell"><span aria-hidden="true">···</span></td>
                  <td className="mobile-detail">
                    <span><small>Forecast</small><strong>{part.forecast} <i>{part.growth}</i></strong></span>
                    <span><small>Current</small><strong>{part.stock}</strong></span>
                    <span><small>Suggested</small><strong>{part.suggested}</strong></span>
                    <b className={`risk-pill risk-${part.risk.toLowerCase()}`}>{part.risk} risk</b>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="fixture-footnote">Illustrative interface values · not connected to business records</p>
    </section>
  )
}
