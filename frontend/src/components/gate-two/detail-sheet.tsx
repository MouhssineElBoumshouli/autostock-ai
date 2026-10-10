import { ArrowRight, Boxes, Building2, Clock3, PackageCheck, Sparkles } from 'lucide-react'
import {
  Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle,
} from '@/components/ui/sheet'
import { developmentDashboardFixture } from '@/data/development-dashboard-fixture'
import { interactiveProducts, type InteractiveProduct } from '@/data/gate-two-fixtures'

export type DashboardDrawer =
  | { type: 'product'; product: InteractiveProduct }
  | { type: 'recommendation'; product: InteractiveProduct }
  | { type: 'health' }
  | { type: 'recommendations' }
  | { type: 'insights' }
  | null

type DetailSheetProps = {
  drawer: DashboardDrawer
  onOpenChange: (open: boolean) => void
  onOpenRecommendation: (product: InteractiveProduct) => void
  onGoToRestock: () => void
}

export function DetailSheet({ drawer, onOpenChange, onOpenRecommendation, onGoToRestock }: DetailSheetProps) {
  const open = drawer !== null
  const product = drawer?.type === 'product' || drawer?.type === 'recommendation' ? drawer.product : null
  const title = product?.name
    ?? (drawer?.type === 'health' ? 'Inventory health' : drawer?.type === 'insights' ? 'Insights for this sample' : 'Restock recommendations')
  const description = drawer?.type === 'product'
    ? `Quick view for ${product?.name}, using local development fixture details.`
    : drawer?.type === 'recommendation'
      ? `Review the sample reorder suggestion for ${product?.name}. No purchase will be created.`
      : drawer?.type === 'health'
        ? 'A closer look at the illustrative stock groups shown on this Dashboard.'
        : drawer?.type === 'insights'
          ? 'A full view of the three illustrative notes on this Dashboard.'
          : 'Review the illustrative items that appear in the reorder preview.'

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="interactive-drawer" side="right">
        <SheetHeader className="interactive-drawer-header">
          <div className="drawer-eyebrow"><span className="drawer-eyebrow-icon"><Sparkles size={14} aria-hidden="true" /></span>Dashboard preview · fixture details</div>
          <SheetTitle className="interactive-drawer-title">{title}</SheetTitle>
          <SheetDescription className="interactive-drawer-description">{description}</SheetDescription>
        </SheetHeader>
        <div className="interactive-drawer-body">
          {product && <ProductDetails product={product} showRecommendation={drawer?.type === 'recommendation'} onGoToRestock={onGoToRestock} />}
          {drawer?.type === 'health' && <HealthDetails />}
          {drawer?.type === 'recommendations' && (
            <div className="drawer-product-list" aria-label="All sample reorder recommendations">
              {interactiveProducts.map((item) => (
                <button className="drawer-list-product" type="button" key={item.sku} onClick={() => onOpenRecommendation(item)}>
                  <span className="drawer-list-icon"><Boxes size={16} aria-hidden="true" /></span>
                  <span><strong>{item.name}</strong><small>{item.sku} · {item.category}</small></span>
                  <span className={`risk-pill risk-${item.risk.toLowerCase()}`}>{item.risk}</span>
                </button>
              ))}
              <p className="fixture-explanation">These are local preview records. The list is not connected to a business inventory.</p>
            </div>
          )}
          {drawer?.type === 'insights' && <InsightDetails />}
        </div>
      </SheetContent>
    </Sheet>
  )
}

function ProductDetails({ product, showRecommendation, onGoToRestock }: {
  product: InteractiveProduct
  showRecommendation: boolean
  onGoToRestock: () => void
}) {
  return (
    <>
      <div className="drawer-part-identity">
        <span className={`part-thumbnail part-thumbnail-${product.icon}`}><PackageCheck size={23} aria-hidden="true" /></span>
        <div><span className="drawer-sku">SKU {product.sku}</span><strong>{product.category}</strong></div>
        <span className={`risk-pill risk-${product.risk.toLowerCase()}`}>{product.risk} priority</span>
      </div>

      <div className="drawer-metric-grid">
        <Metric label="Current stock" value={`${product.stock} units`} />
        <Metric label="Suggested order" value={`${product.suggested} units`} />
        <Metric label="Expected demand · 30 days" value={`${product.forecast} units`} />
        <Metric label="Supplier lead time" value={`${product.leadTimeDays} days`} />
      </div>

      <section className="drawer-info-section">
        <h3><Building2 size={15} aria-hidden="true" />Supplier</h3>
        <p>{product.supplier}</p>
        <span><Clock3 size={14} aria-hidden="true" />Typical delivery in {product.leadTimeDays} days in this fixture</span>
      </section>

      <section className="drawer-info-section">
        <h3><Boxes size={15} aria-hidden="true" />Commonly used for</h3>
        <div className="fitment-tags">{product.vehicles.map((vehicle) => <span key={vehicle}>{vehicle}</span>)}</div>
      </section>

      {showRecommendation && (
        <section className="recommendation-reason">
          <h3>Why this recommendation?</h3>
          <p>{product.reason}</p>
          <details className="calculation-disclosure">
            <summary>How calculated?</summary>
            <ul>{product.calculationNotes.map((note) => <li key={note}>{note}</li>)}</ul>
            <p className="disclosure-footnote">Illustrative example only · no live stock or forecast calculations.</p>
          </details>
        </section>
      )}

      {!showRecommendation && <p className="fixture-explanation">This quick view uses local preview details. It does not open a business record or contact a supplier.</p>}

      <div className="drawer-footer-actions">
        <button className="drawer-secondary-action" type="button" onClick={onGoToRestock}>View in restock list <ArrowRight size={15} aria-hidden="true" /></button>
        <span>Purchasing is not enabled in this preview.</span>
      </div>
    </>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="drawer-metric"><span>{label}</span><strong>{value}</strong></div>
}

function HealthDetails() {
  return (
    <>
      <div className="health-detail-list">
        {developmentDashboardFixture.health.segments.map((segment) => (
          <div className="health-detail-row" key={segment.label}>
            <span><i className={`health-dot health-dot-${segment.color}`} />{segment.label}</span>
            <strong>{segment.count}</strong><b>{segment.percent}%</b>
          </div>
        ))}
      </div>
      <div className="drawer-note"><strong>What this means</strong><p>These groups help you spot what is available, running low, or out of stock in the sample view.</p></div>
      <p className="fixture-explanation">Illustrative fixture totals only. No Odoo products or stock quantities are loaded.</p>
    </>
  )
}

function InsightDetails() {
  return (
    <div className="drawer-insight-list">
      {developmentDashboardFixture.insights.map((insight) => (
        <article className="drawer-insight" key={insight.title}>
          <h3>{insight.title}</h3><p>{insight.description}</p>
          <span>{insight.action} is a preview action. No order or inventory change will be made.</span>
        </article>
      ))}
      <p className="fixture-explanation">All figures and observations in these cards are development fixtures.</p>
    </div>
  )
}
