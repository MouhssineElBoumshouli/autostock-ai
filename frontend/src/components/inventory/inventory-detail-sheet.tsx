import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, ArrowDownToLine, ArrowUpFromLine, Boxes, Building2, Clock3, LoaderCircle, PackageCheck, Repeat2, Truck } from 'lucide-react'
import { api, ApiError } from '@/api/client'
import type { InventoryData, InventoryDetailData } from '@/api/contracts'
import {
  Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle,
} from '@/components/ui/sheet'

type ProductStub = InventoryData['items'][number] | {
  product_id: number
  name: string
  sku: string
  reference: string | false
  category: string
}

function quantity(value: number, unit: string) {
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value)} ${unit}`
}

function movementIcon(kind: string) {
  if (kind === 'received' || kind === 'incoming_purchase') return ArrowDownToLine
  if (kind === 'shipped' || kind === 'reserved_delivery' || kind === 'scheduled_delivery') return ArrowUpFromLine
  if (kind === 'internal_transfer' || kind === 'internal_transfer_planned') return Repeat2
  if (kind === 'adjustment') return PackageCheck
  return Truck
}

function movementDate(value: string | false, locale: string, timezone: string) {
  if (!value) return 'Date unavailable'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const normalizedLocale = locale.replaceAll('_', '-')
  try {
    return new Intl.DateTimeFormat(normalizedLocale, {
      dateStyle: 'medium',
      timeStyle: 'short',
      timeZone: timezone || undefined,
    }).format(date)
  } catch {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(date)
  }
}

function DetailLoading() {
  return (
    <div className="inventory-detail-state" role="status">
      <LoaderCircle className="inventory-spin" size={20} aria-hidden="true" />
      <strong>Loading part details</strong>
      <p>Checking the latest stock and activity for this part.</p>
    </div>
  )
}

function DetailError({ message, retry, forbidden }: { message: string; retry: () => void; forbidden: boolean }) {
  return (
    <div className="inventory-detail-state" role="alert">
      <AlertTriangle size={20} aria-hidden="true" />
      <strong>{forbidden ? 'Part details are not available to your role' : 'Part details could not be loaded'}</strong>
      <p>{message}</p>
      {!forbidden && <button className="inventory-retry" type="button" onClick={retry}>Try again</button>}
    </div>
  )
}

function Metric({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="inventory-detail-metric">
      <span>{label}</span>
      <strong>{value}</strong>
      {note && <small>{note}</small>}
    </div>
  )
}

function ProductInventoryDetails({ data, locale, timezone, selectedWarehouseId }: {
  data: InventoryDetailData
  locale: string
  timezone: string
  selectedWarehouseId?: number
}) {
  const { product, company_stock: stock } = data
  const selectedRecommendation = selectedWarehouseId
    ? data.recommendations.find((item) => item.warehouse_id === selectedWarehouseId)
    : data.recommendations.find((item) => item.reorder_needed) ?? data.recommendations[0]
  const trackedRecommendation = product.tracked ? selectedRecommendation : undefined

  return (
    <div className="inventory-detail-content">
      <section className="inventory-detail-block inventory-stock-overview" aria-labelledby="inventory-stock-title">
        <div className="inventory-detail-section-heading">
          <h3 id="inventory-stock-title">Company-wide stock</h3>
          <span>Across all visible warehouses</span>
        </div>
        <div className="inventory-detail-metrics">
          <Metric label="On hand" value={quantity(stock.on_hand, product.uom)} note="Physical stock" />
          <Metric label="Available to use" value={quantity(stock.available, product.uom)} note="Not reserved" />
          <Metric label="Reserved" value={quantity(stock.reserved, product.uom)} note="For active work" />
          <Metric label="Incoming" value={quantity(stock.incoming, product.uom)} note="Expected receipts" />
        </div>
        <div className="inventory-projection-line">
          <span>Outgoing <strong>{quantity(stock.outgoing, product.uom)}</strong></span>
          <span>After expected moves <strong>{quantity(stock.projected, product.uom)}</strong></span>
        </div>
      </section>

      <section className="inventory-detail-block" aria-labelledby="inventory-warehouse-title">
        <div className="inventory-detail-section-heading">
          <h3 id="inventory-warehouse-title"><Boxes size={15} aria-hidden="true" /> Stock by warehouse</h3>
          <span>{data.coverage.total_warehouses} {data.coverage.total_warehouses === 1 ? 'warehouse' : 'warehouses'}</span>
        </div>
        {data.warehouses.length ? (
          <div className="inventory-warehouse-list">
            {data.warehouses.map((warehouse) => (
              <article className={`inventory-warehouse-card${warehouse.selected || warehouse.id === selectedWarehouseId ? ' is-selected' : ''}`} key={warehouse.id}>
                <div className="inventory-warehouse-heading">
                  <strong>{warehouse.name}</strong>
                  {(warehouse.selected || warehouse.id === selectedWarehouseId) && <span>Selected</span>}
                </div>
                <div className="inventory-warehouse-values">
                  <span>On hand <strong>{quantity(warehouse.on_hand, product.uom)}</strong></span>
                  <span>Available to use <strong>{quantity(warehouse.available, product.uom)}</strong></span>
                  <span>Reserved <strong>{quantity(warehouse.reserved, product.uom)}</strong></span>
                  <span>Incoming <strong>{quantity(warehouse.incoming, product.uom)}</strong></span>
                  <span>Outgoing <strong>{quantity(warehouse.outgoing, product.uom)}</strong></span>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="inventory-inline-note">No warehouse stock is visible in this company.</div>
        )}
        {data.coverage.warehouse_scope_limited && (
          <p className="inventory-coverage-note">Warehouse coverage is limited to the first 50 visible locations. The totals above still use Odoo’s company-wide quantity fields.</p>
        )}
      </section>

      <section className="inventory-detail-block" aria-labelledby="inventory-supplier-title">
        <div className="inventory-detail-section-heading">
          <h3 id="inventory-supplier-title"><Building2 size={15} aria-hidden="true" /> Supplier and delivery</h3>
        </div>
        {data.supplier ? (
          <div className="inventory-supplier-card">
            <strong>{data.supplier.name}</strong>
            <span><Clock3 size={14} aria-hidden="true" />{data.supplier.lead_time_label}: {data.supplier.lead_time_days} days</span>
            {data.supplier.minimum_order_qty > 0 && <span>Supplier minimum: {quantity(data.supplier.minimum_order_qty, data.supplier.minimum_order_uom)}</span>}
          </div>
        ) : (
          <div className="inventory-inline-note">
            <strong>{data.supplier_access ? 'No supplier on file' : 'Supplier details are restricted'}</strong>
            <p>{data.supplier_note || 'A supplier is not recorded for this part.'}</p>
            {data.lead_time_source === 'planning_assumption' && <span>{data.lead_time_label}: {data.lead_time_days} days</span>}
          </div>
        )}
      </section>

      <section className="inventory-detail-block" aria-labelledby="inventory-forecast-title">
        <div className="inventory-detail-section-heading">
          <h3 id="inventory-forecast-title"><Truck size={15} aria-hidden="true" /> Demand outlook</h3>
        </div>
        <div className={`inventory-forecast-note is-${data.forecast.status}`}>
          <strong>{data.forecast.status === 'used' ? 'Reviewed delivery forecast available' : data.forecast.status === 'not_used' ? 'Saved forecast not used for restock guidance' : data.forecast.status === 'not_tracked' ? 'Monitoring is not enabled' : 'No eligible forecast available'}</strong>
          <p>{data.forecast.message}</p>
          {data.forecast.used_for_restock && data.forecast.demand_before_delivery !== false && (
            <span>Forecast demand before delivery: {quantity(data.forecast.demand_before_delivery, product.uom)}</span>
          )}
          {data.forecast.history_start && data.forecast.history_end && (
            <small>Delivery history: {data.forecast.history_start} to {data.forecast.history_end}</small>
          )}
        </div>
      </section>

      <section className="inventory-detail-block" aria-labelledby="inventory-restock-title">
        <div className="inventory-detail-section-heading">
          <h3 id="inventory-restock-title">Restock guidance</h3>
          <span>Read-only</span>
        </div>
        {!product.tracked ? (
          <div className="inventory-inline-note">This part is not enabled for AutoStock monitoring, so no restock guidance is shown.</div>
        ) : trackedRecommendation ? (
          <article className="inventory-recommendation-card">
            <div className="inventory-recommendation-topline">
              <span>{trackedRecommendation.warehouse}</span>
              <span className={`inventory-status is-${trackedRecommendation.status === 'out' || trackedRecommendation.status === 'shortage' ? 'out_of_stock' : trackedRecommendation.status === 'low' ? 'low_stock' : 'in_stock'}`}>{trackedRecommendation.status_label}</span>
            </div>
            {trackedRecommendation.recommended_qty !== false ? (
              <strong className="inventory-recommendation-quantity">Review a restock of {quantity(trackedRecommendation.recommended_qty, trackedRecommendation.uom)}</strong>
            ) : (
              <strong className="inventory-recommendation-quantity">No restock quantity is recommended</strong>
            )}
            <p>{trackedRecommendation.reason}</p>
            <details className="inventory-disclosure">
              <summary>How calculated?</summary>
              <ul>
                <li>{trackedRecommendation.basis_note}</li>
                <li>Reorder rule: {trackedRecommendation.policy_source_label}.</li>
                <li>{trackedRecommendation.lead_time_label}: {trackedRecommendation.lead_time_days} days.</li>
                {trackedRecommendation.forecast_used && <li>A reviewed delivery forecast contributed demand through the expected delivery date.</li>}
                {trackedRecommendation.policy_issue && <li>{trackedRecommendation.policy_issue}</li>}
              </ul>
              <small>Guidance only. Review stock and the reorder rule before acting.</small>
            </details>
          </article>
        ) : (
          <div className="inventory-inline-note">
            {data.recommendation_coverage.complete
              ? 'No warehouse restock recommendation is available for this part.'
              : 'The recommendation lookup is partial, so a complete restock summary is not available.'}
          </div>
        )}
      </section>

      <section className="inventory-detail-block" aria-labelledby="inventory-movements-title">
        <div className="inventory-detail-section-heading">
          <h3 id="inventory-movements-title"><Repeat2 size={15} aria-hidden="true" /> Recent stock activity</h3>
          <span>Recent changes and expected activity</span>
        </div>
        {!data.movements_available ? (
          <div className="inventory-inline-note">{data.movement_note}</div>
        ) : data.movements.length ? (
          <ol className="inventory-movement-list">
            {data.movements.map((movement) => {
              const Icon = movementIcon(movement.kind)
              return (
                <li key={movement.id}>
                  <span className={`inventory-movement-icon is-${movement.kind}`}><Icon size={15} aria-hidden="true" /></span>
                  <div className="inventory-movement-copy">
                    <strong>{movement.label}</strong>
                    <span>{movementDate(movement.date, locale, timezone)}{movement.warehouse ? ` · ${movement.warehouse}` : ''}</span>
                    {movement.reference && <small>{movement.reference}</small>}
                  </div>
                  <b>{quantity(movement.quantity, movement.uom)}</b>
                </li>
              )
            })}
          </ol>
        ) : (
          <div className="inventory-inline-note">No stock changes were recorded in the last 90 days.</div>
        )}
        <p className="inventory-movement-footnote">{data.movement_note}</p>
      </section>
    </div>
  )
}

export function InventoryDetailSheet({ product, companyId, warehouseId, locale, timezone, onClose }: {
  product: ProductStub | null
  companyId: number
  warehouseId?: number
  locale: string
  timezone: string
  onClose: () => void
}) {
  const open = product !== null
  const detail = useQuery({
    queryKey: ['inventory-detail', companyId, product?.product_id, warehouseId ?? null],
    queryFn: () => api.inventoryDetail(companyId, product!.product_id, warehouseId),
    enabled: open,
  })
  const title = detail.data?.product.name ?? product?.name ?? 'Part details'
  const description = detail.data
    ? `Stock, supplier, and recent activity for ${detail.data.product.name}.`
    : 'Stock, supplier, and recent activity for the selected company.'
  const forbidden = detail.error instanceof ApiError && detail.error.code === 'forbidden'

  return (
    <Sheet open={open} onOpenChange={(next) => { if (!next) onClose() }}>
      <SheetContent className="interactive-drawer inventory-detail-sheet" side="right">
        <SheetHeader className="interactive-drawer-header">
          <div className="drawer-eyebrow"><span className="drawer-eyebrow-icon"><PackageCheck size={14} aria-hidden="true" /></span>Company data · read-only</div>
          <SheetTitle className="interactive-drawer-title">{title}</SheetTitle>
          <SheetDescription className="interactive-drawer-description">{description}</SheetDescription>
          {product && (
            <div className="inventory-detail-identifiers">
              <span>SKU <strong>{detail.data?.product.sku ?? product.sku}</strong></span>
              {(detail.data?.product.reference ?? product.reference) && <span>OEM reference <strong>{detail.data?.product.reference ?? product.reference}</strong></span>}
              {detail.data && <span>{detail.data.product.category}</span>}
            </div>
          )}
        </SheetHeader>
        <div className="interactive-drawer-body inventory-detail-body">
          {detail.isPending ? <DetailLoading /> : detail.isError ? (
            <DetailError message={detail.error.message} retry={() => void detail.refetch()} forbidden={forbidden} />
          ) : detail.data ? (
            <ProductInventoryDetails
              data={detail.data}
              locale={locale}
              timezone={timezone}
              selectedWarehouseId={warehouseId}
            />
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  )
}
