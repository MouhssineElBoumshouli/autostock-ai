import { PencilIcon, XIcon } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";

import { type PartDetail, usePart } from "@/api/stock";
import { ErrorState } from "@/components/ErrorState";
import { useSignedIn } from "@/components/SignedIn";
import { StockBadge } from "@/components/StockBadge";
import { Button } from "@/components/ui/button";
import { Sheet, SheetClose, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";
import { formatDay, formatMoney, formatNumber } from "@/lib/format";

import { PartEditForm } from "./PartEditForm";

// Everything about one part, sliding in from the end side. Owners and managers can edit it here.
export function PartPanel({ partId, canEdit, onClose }: { partId: string | null; canEdit: boolean; onClose: () => void }) {
  const part = usePart(partId);
  const [editing, setEditing] = useState(false);

  useEffect(() => setEditing(false), [partId]);

  return (
    <Sheet open={partId !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="end" className="w-full overflow-y-auto sm:max-w-lg">
        {part.isError ? (
          <>
            <SheetTitle className="sr-only">{t.nav.stock}</SheetTitle>
            <ErrorState onRetry={() => part.refetch()} retrying={part.isFetching} />
          </>
        ) : !part.data ? (
          <div className="grid gap-4 p-6" aria-busy="true">
            <SheetTitle className="sr-only">{t.nav.stock}</SheetTitle>
            <Skeleton className="h-7 w-2/3" />
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
        ) : editing ? (
          <PartEditForm part={part.data} onDone={() => setEditing(false)} />
        ) : (
          <PartDetails part={part.data} canEdit={canEdit} onEdit={() => setEditing(true)} />
        )}
      </SheetContent>
    </Sheet>
  );
}

function PartDetails({ part, canEdit, onEdit }: { part: PartDetail; canEdit: boolean; onEdit: () => void }) {
  const currency = useSignedIn().organization.currency;

  return (
    <div className="flex min-h-full flex-col">
      <header className="flex items-start gap-3 border-b p-6">
        <div className="grid min-w-0 flex-1 gap-1">
          <SheetTitle className="text-lg font-semibold">{part.name}</SheetTitle>
          <p className="text-sm text-muted-foreground">
            {[part.sku, part.brand].filter(Boolean).join(" · ")}
          </p>
          <div className="mt-1">
            <StockBadge status={part.status} />
          </div>
        </div>
        <SheetClose asChild>
          <Button variant="subtle" size="icon-sm" aria-label={t.common.close}>
            <XIcon aria-hidden="true" />
          </Button>
        </SheetClose>
      </header>

      <div className="grid flex-1 content-start gap-6 p-6">
        <Section title={t.part.stockPerBranch}>
          <dl className="divide-y rounded-lg border">
            {part.stock.map((row) => (
              <Line key={row.branch_id} label={row.branch} value={formatNumber(row.quantity)} />
            ))}
            <Line label={t.part.total} value={formatNumber(part.quantity)} strong />
          </dl>
        </Section>

        <Section title={t.part.prices}>
          <dl className="divide-y rounded-lg border">
            <Line label={t.part.unitCost} value={formatMoney(part.unit_cost, currency)} />
            <Line label={t.part.salePrice} value={formatMoney(part.sale_price, currency)} />
            <Line label={t.part.minStock} value={formatNumber(part.min_stock)} />
          </dl>
        </Section>

        <Section title={t.part.details}>
          <dl className="divide-y rounded-lg border">
            <Line label={t.part.category} value={part.category ?? t.common.notSet} />
            <Line label={t.part.oem} value={part.oem_reference ?? t.common.notSet} />
          </dl>
        </Section>

        <Section title={t.part.supplier}>
          {part.supplier ? (
            <div className="grid gap-1 rounded-lg border px-4 py-3 text-sm">
              <p className="font-medium">{part.supplier.name}</p>
              {part.supplier.phone && (
                <a href={`tel:${part.supplier.phone}`} className="w-fit text-muted-foreground hover:text-foreground">
                  {part.supplier.phone}
                </a>
              )}
              {part.supplier.email && (
                <a href={`mailto:${part.supplier.email}`} className="w-fit text-muted-foreground hover:text-foreground">
                  {part.supplier.email}
                </a>
              )}
              {part.supplier.delivery_days !== null && (
                <p className="text-muted-foreground">{t.part.deliveryDays(part.supplier.delivery_days)}</p>
              )}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">{t.part.noSupplier}</p>
          )}
        </Section>

        <Section title={t.part.lastSales}>
          {part.last_sales.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t.part.noSales}</p>
          ) : (
            <ul className="divide-y rounded-lg border">
              {part.last_sales.map((sale, index) => (
                <li key={index} className="flex items-center justify-between gap-4 px-4 py-2.5 text-sm">
                  <span>
                    {formatDay(sale.sold_on)}
                    <span className="text-muted-foreground"> · {sale.branch}</span>
                  </span>
                  <span className="text-end tabular-nums">
                    {t.part.sold(formatNumber(sale.quantity))}
                    {sale.unit_price !== null && (
                      <span className="block text-xs text-muted-foreground">{formatMoney(sale.unit_price, currency)}</span>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Section>
      </div>

      {canEdit && (
        <footer className="sticky bottom-0 border-t bg-card p-4">
          <Button variant="primary" className="w-full" onClick={onEdit}>
            <PencilIcon aria-hidden="true" />
            {t.part.edit}
          </Button>
        </footer>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="grid gap-2">
      <h3 className="text-sm font-semibold">{title}</h3>
      {children}
    </section>
  );
}

function Line({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4 px-4 py-2.5 text-sm">
      <dt className={strong ? "font-medium" : "text-muted-foreground"}>{label}</dt>
      <dd className={strong ? "font-semibold tabular-nums" : "tabular-nums"}>{value}</dd>
    </div>
  );
}
