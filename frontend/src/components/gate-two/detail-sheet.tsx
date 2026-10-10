import { AlertTriangle, ArrowRight, Boxes, Building2, Clock3, LoaderCircle, PackageCheck, Sparkles } from 'lucide-react'
import type { DashboardData, DashboardInsight, ProductQuickViewData, RestockData, RiskItem } from '@/api/contracts'
import {
  Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle,
} from '@/components/ui/sheet'

export type DashboardDrawer =
  | { type: 'product'; product: ProductQuickViewData }
  | { type: 'product-loading'; name: string }
  | { type: 'product-error'; name: string; message: string }
  | { type: 'recommendation'; product: RiskItem }
  | { type: 'health' }
  | { type: 'recommendations' }
  | { type: 'insights' }
  | null

type DetailSheetProps = {
  drawer: DashboardDrawer
  health?: DashboardData['inventory_health']
  restock?: RestockData
  insights?: DashboardInsight[]
  onOpenChange: (open: boolean) => void
  onRetryProduct?: () => void
  onOpenRecommendation: (product: RiskItem) => void
  onGoToRestock: () => void
}

function formatQuantity(value: number | false, unit: string) {
  return value === false ? 'Not available' : `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value)} ${unit}`
}

function riskTone(item: RiskItem) {
  if (item.status === 'out' || item.status === 'shortage') return 'high'
  if (item.status === 'low') return 'medium'
  return 'review'
}

export function DetailSheet({ drawer, health, restock, insights = [], onOpenChange, onRetryProduct, onOpenRecommendation, onGoToRestock }: DetailSheetProps) {
  const open = drawer !== null
  const product = drawer?.type === 'product' ? drawer.product.product : null
  const recommendation = drawer?.type === 'recommendation' ? drawer.product : null
  const title = product?.name
    ?? (drawer?.type === 'product-loading' || drawer?.type === 'product-error' ? drawer.name : null)
    ?? recommendation?.name
    ?? (drawer?.type === 'health' ? 'Inventory health' : drawer?.type === 'insights' ? 'Current stock insights' : 'Top restock recommendations')
  const description = drawer?.type === 'product'
    ? `Current company details for ${product?.name}.`
    : drawer?.type === 'recommendation'
      ? `Review current stock at ${recommendation?.warehouse} and the read-only reorder guidance for ${recommendation?.name}.`
      : drawer?.type === 'health'
        ? 'A closer look at the inventory counts returned for the selected company.'
        : drawer?.type === 'insights'
          ? 'These observations summarize current stock and recommendation coverage.'
          : 'The five highest-priority part locations found in the current scan.'

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="interactive-drawer" side="right">
        <SheetHeader className="interactive-drawer-header">
          <div className="drawer-eyebrow"><span className="drawer-eyebrow-icon"><Sparkles size={14} aria-hidden="true" /></span>Company data · read-only</div>
          <SheetTitle className="interactive-drawer-title">{title}</SheetTitle>
          <SheetDescription className="interactive-drawer-description">{description}</SheetDescription>
        </SheetHeader>
        <div className="interactive-drawer-body">
          {drawer?.type === 'product' && <QuickView product={drawer.product} onOpenRecommendation={onOpenRecommendation} onGoToRestock={onGoToRestock} />}
          {drawer?.type === 'product-loading' && (
            <div className="drawer-load-state" role="status">
              <LoaderCircle className="drawer-state-icon is-loading" size={20} aria-hidden="true" />
              <p>Loading this part from your current Odoo company…</p>
            </div>
          )}
          {drawer?.type === 'product-error' && (
            <div className="drawer-load-state" role="alert">
              <AlertTriangle className="drawer-state-icon" size={20} aria-hidden="true" />
              <p>{drawer.message}</p>
              <button className="inline-retry-button" type="button" onClick={onRetryProduct}>Try again</button>
            </div>
          )}
          {recommendation && <ProductDetails product={recommendation} onGoToRestock={onGoToRestock} />}
          {drawer?.type === 'health' && health && <HealthDetails health={health} />}
          {drawer?.type === 'recommendations' && restock && (
            <div className="drawer-product-list" aria-label="Top restock recommendations">
              {restock.items.map((item) => (
                <button className="drawer-list-product" type="button" key={item.key} onClick={() => onOpenRecommendation(item)}>
                  <span className="drawer-list-icon"><Boxes size={16} aria-hidden="true" /></span>
                  <span><strong>{item.name}</strong><small>{item.sku} · {item.category} · {item.warehouse}</small></span>
                  <span className={`risk-pill risk-${riskTone(item)}`}>{item.status_label}</span>
                </button>
              ))}
              <p className="drawer-note">Showing up to five recommendations from this company scan. {restock.coverage.complete ? 'The scan is complete.' : `${restock.coverage.scanned_locations} of ${restock.coverage.candidate_locations} part locations were checked.`}</p>
              <ReadOnlyFooter />
            </div>
          )}
          {drawer?.type === 'insights' && <InsightDetails insights={insights} restock={restock} />}
        </div>
      </SheetContent>
    </Sheet>
  )
}

function QuickView({ product, onOpenRecommendation, onGoToRestock }: {
  product: ProductQuickViewData
  onOpenRecommendation: (product: RiskItem) => void
  onGoToRestock: () => void
}) {
  const firstPosition = product.positions[0]
  return (
    <>
      <div className="drawer-part-identity">
        <span className="part-thumbnail part-thumbnail-brake"><PackageCheck size={23} aria-hidden="true" /></span>
        <div><span className="drawer-sku">SKU {product.product.sku}</span><strong>{product.product.category}</strong></div>
        {firstPosition && <span className={`risk-pill risk-${riskTone(firstPosition)}`}>{firstPosition.status_label}</span>}
      </div>

      {firstPosition ? <ProductMetrics product={firstPosition} /> : (
        <div className="drawer-note"><strong>{product.product.tracked ? 'No stock details available' : 'Not tracked for stock recommendations'}</strong><p>{product.product.tracked ? 'Stock details are unavailable for this part in the selected company.' : 'This part is in the company catalog but is not enabled for AutoStock stock monitoring.'}</p></div>
      )}

      {firstPosition && <ProductSupplier product={firstPosition} />}
      {product.positions.length > 1 && (
        <section className="drawer-info-section">
          <h3><Boxes size={15} aria-hidden="true" />Other warehouses</h3>
          <div className="drawer-product-list">
            {product.positions.slice(1).map((position) => (
              <button className="drawer-list-product" type="button" key={position.key} onClick={() => onOpenRecommendation(position)}>
                <span className="drawer-list-icon"><Boxes size={16} aria-hidden="true" /></span>
                <span><strong>{position.warehouse}</strong><small>{formatQuantity(position.current_qty, position.uom)} on hand</small></span>
                <span className={`risk-pill risk-${riskTone(position)}`}>{position.status_label}</span>
              </button>
            ))}
          </div>
        </section>
      )}
      {!product.coverage.complete && <p className="drawer-note">Warehouse coverage is partial: {product.coverage.scanned_locations} of {product.coverage.candidate_locations} part locations were checked.</p>}
      <div className="drawer-footer-actions">
        <button className="drawer-secondary-action" type="button" onClick={onGoToRestock}>View restock recommendations <ArrowRight size={15} aria-hidden="true" /></button>
        <span>Purchasing is read-only.</span>
      </div>
    </>
  )
}

function ProductDetails({ product, onGoToRestock }: { product: RiskItem; onGoToRestock: () => void }) {
  return (
    <>
      <div className="drawer-part-identity">
        <span className="part-thumbnail part-thumbnail-brake"><PackageCheck size={23} aria-hidden="true" /></span>
        <div><span className="drawer-sku">SKU {product.sku}</span><strong>{product.category}</strong></div>
        <span className={`risk-pill risk-${riskTone(product)}`}>{product.status_label}</span>
      </div>

      <ProductMetrics product={product} />
      <ProductSupplier product={product} />

      <section className="recommendation-reason">
        <h3>{product.reorder_needed ? 'Why this recommendation?' : 'Current stock at this warehouse'}</h3>
        <p>{product.reorder_needed ? product.reason : 'No order quantity is recommended for this part at this warehouse.'}</p>
        <details className="calculation-disclosure">
          <summary>How calculated?</summary>
          <ul>
            <li>{product.basis_note}</li>
            <li>Reorder rule: {product.policy_source_label}.</li>
            <li>Planning time: {product.lead_time_label}, {product.lead_time_days} days.</li>
            {product.forecast_used && <li>A reviewed delivery forecast contributed demand through the expected receipt date.</li>}
            {product.policy_issue && <li>{product.policy_issue}</li>}
          </ul>
          <p className="disclosure-footnote">Guidance only. Review stock and the reorder rule before acting.</p>
        </details>
      </section>

      <div className="drawer-footer-actions">
        <button className="drawer-secondary-action" type="button" onClick={onGoToRestock}>View in restock list <ArrowRight size={15} aria-hidden="true" /></button>
        <span>Purchasing is read-only.</span>
      </div>
    </>
  )
}

function ProductMetrics({ product }: { product: RiskItem }) {
  return (
    <>
      <div className="drawer-location-label"><Boxes size={14} aria-hidden="true" />{product.warehouse}</div>
      <div className="drawer-metric-grid">
        <Metric label="Current stock" value={formatQuantity(product.current_qty, product.uom)} />
        <Metric label="Available to use" value={formatQuantity(product.free_qty, product.uom)} />
        <Metric label="Suggested order" value={formatQuantity(product.recommended_qty, product.uom)} />
        <Metric label="Demand before delivery" value={product.forecast_used ? formatQuantity(product.forecast_demand, product.uom) : 'No forecast'} />
      </div>

      <section className="drawer-info-section">
        <h3><Boxes size={15} aria-hidden="true" />Stock movement</h3>
        <div className="drawer-fact-list">
          <span>Reserved for customer orders <strong>{formatQuantity(product.reserved_qty, product.uom)}</strong></span>
          <span>Incoming by expected delivery <strong>{formatQuantity(product.incoming_qty, product.uom)}</strong></span>
          <span>Outgoing before expected delivery <strong>{formatQuantity(product.outgoing_qty, product.uom)}</strong></span>
          <span>Projected at expected delivery <strong>{formatQuantity(product.projected_qty, product.uom)}</strong></span>
          {product.forecast_used && <span>Projected after reviewed demand <strong>{formatQuantity(product.projected_after_demand, product.uom)}</strong></span>}
        </div>
      </section>
    </>
  )
}

function ProductSupplier({ product }: { product: RiskItem }) {
  return (
    <section className="drawer-info-section">
      <h3><Building2 size={15} aria-hidden="true" />Supplier and delivery</h3>
      <p>{product.supplier_name || 'Supplier terms are not available'}</p>
      <span><Clock3 size={14} aria-hidden="true" />{product.lead_time_label}: {product.lead_time_days} days</span>
      {product.supplier && product.supplier.minimum_qty > 0 && <span>Minimum order: {formatQuantity(product.supplier.minimum_qty, product.supplier.minimum_uom)}</span>}
      {product.supplier_access_note && <small className="drawer-muted-note">{product.supplier_access_note}</small>}
      {!product.forecast_used && product.forecast_reason && <small className="drawer-muted-note">Demand forecast not used: {product.forecast_reason}</small>}
    </section>
  )
}

function HealthDetails({ health }: { health: DashboardData['inventory_health'] }) {
  const colors = { healthy: 'green', low: 'amber', out: 'red' } as const
  return (
    <>
      <div className="health-detail-list">
        {health.categories.map((segment) => (
          <div className="health-detail-row" key={segment.key}>
            <span><i className={`health-dot health-dot-${colors[segment.key]}`} />{segment.label}</span>
            <strong>{new Intl.NumberFormat().format(segment.count)}</strong><b>{segment.percent}%</b>
          </div>
        ))}
      </div>
      <div className="drawer-note"><strong>What this means</strong><p>These counts show the tracked parts that are in stock, at or below their safety stock, or out of stock.</p></div>
      <p className="drawer-muted-note">{health.complete ? `All ${new Intl.NumberFormat().format(health.total_tracked)} tracked parts are included.` : `${new Intl.NumberFormat().format(health.sampled_products)} of ${new Intl.NumberFormat().format(health.total_tracked)} tracked parts are included in this summary.`}</p>
    </>
  )
}

function InsightDetails({ insights, restock }: { insights: DashboardInsight[]; restock?: RestockData }) {
  return (
    <div className="drawer-insight-list">
      {insights.map((insight) => (
        <article className="drawer-insight" key={insight.id}>
          <h3>{insight.title}</h3><p>{insight.description}</p>
          <span>{insight.action_label} opens the current read-only recommendations.</span>
        </article>
      ))}
      {restock && <p className="drawer-muted-note">Coverage: {restock.coverage.scanned_locations} of {restock.coverage.candidate_locations} part locations scanned.</p>}
      <ReadOnlyFooter />
    </div>
  )
}

function ReadOnlyFooter() {
  return <div className="drawer-note"><strong>Read-only guidance</strong><p>AutoStock does not place orders or change stock from this Dashboard.</p></div>
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="drawer-metric"><span>{label}</span><strong>{value}</strong></div>
}
