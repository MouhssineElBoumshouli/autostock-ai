import { Link2Icon, PencilIcon, XIcon } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import { toast } from "sonner";

import {
  type EquivalentPart,
  type PartDetail,
  useAddEquivalent,
  useParts,
  usePart,
  useRemoveEquivalent,
} from "@/api/stock";
import { ErrorState } from "@/components/ErrorState";
import { FormError } from "@/components/FormError";
import { useSignedIn } from "@/components/SignedIn";
import { StockBadge } from "@/components/StockBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
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
  const outOfStock = part.status === "out";

  const equivalentsSection = (
    <Section title={t.part.equivalents.title}>
      <div className="grid gap-3">
        {part.equivalents.length === 0 ? (
          <p className="text-body-medium text-on-surface-variant">{t.part.equivalents.none}</p>
        ) : (
          <ul className="divide-y rounded-md border">
            {part.equivalents.map((equivalent) => (
              <EquivalentRow key={equivalent.part_id} partId={part.id} equivalent={equivalent} canEdit={canEdit} currency={currency} />
            ))}
          </ul>
        )}
        {canEdit && <AddEquivalentButton part={part} />}
      </div>
    </Section>
  );

  return (
    <div className="flex min-h-full flex-col">
      <header className="flex items-start gap-3 border-b p-6">
        <div className="grid min-w-0 flex-1 gap-1">
          <SheetTitle className="text-headline-small">{part.name}</SheetTitle>
          <p className="text-body-medium text-on-surface-variant">
            {[part.sku, part.brand].filter(Boolean).join(" · ")}
          </p>
          <div className="mt-1">
            <StockBadge status={part.status} />
          </div>
        </div>
        <SheetClose asChild>
          <Button variant="text" size="icon-sm" aria-label={t.common.close}>
            <XIcon aria-hidden="true" />
          </Button>
        </SheetClose>
      </header>

      <div className="grid flex-1 content-start gap-6 p-6">
        {/* Out of stock: the employee's next question is "what else can I sell them", so the
            same-part-other-brands section comes first. In stock, it stays further down. */}
        {outOfStock && equivalentsSection}

        <Section title={t.part.stockPerBranch}>
          <dl className="divide-y rounded-md border">
            {part.stock.map((row) => (
              <Line key={row.branch_id} label={row.branch} value={formatNumber(row.quantity)} />
            ))}
            <Line label={t.part.total} value={formatNumber(part.quantity)} strong />
          </dl>
        </Section>

        <Section title={t.part.prices}>
          <dl className="divide-y rounded-md border">
            <Line label={t.part.unitCost} value={formatMoney(part.unit_cost, currency)} />
            <Line label={t.part.salePrice} value={formatMoney(part.sale_price, currency)} />
            <Line label={t.part.minStock} value={formatNumber(part.min_stock)} />
          </dl>
        </Section>

        <Section title={t.part.details}>
          <dl className="divide-y rounded-md border">
            <Line label={t.part.category} value={part.category ?? t.common.notSet} />
            <Line label={t.part.oem} value={part.oem_reference ?? t.common.notSet} />
          </dl>
        </Section>

        {!outOfStock && equivalentsSection}

        <Section title={t.part.supplier}>
          {part.supplier ? (
            <div className="grid gap-1 rounded-md border px-4 py-3 text-body-medium">
              <p className="font-medium">{part.supplier.name}</p>
              {part.supplier.phone && (
                <a href={`tel:${part.supplier.phone}`} className="w-fit text-on-surface-variant hover:text-on-surface">
                  {part.supplier.phone}
                </a>
              )}
              {part.supplier.email && (
                <a href={`mailto:${part.supplier.email}`} className="w-fit text-on-surface-variant hover:text-on-surface">
                  {part.supplier.email}
                </a>
              )}
              {part.supplier.delivery_days !== null && (
                <p className="text-on-surface-variant">{t.part.deliveryDays(part.supplier.delivery_days)}</p>
              )}
            </div>
          ) : (
            <p className="text-body-medium text-on-surface-variant">{t.part.noSupplier}</p>
          )}
        </Section>

        <Section title={t.part.lastSales}>
          {part.last_sales.length === 0 ? (
            <p className="text-body-medium text-on-surface-variant">{t.part.noSales}</p>
          ) : (
            <ul className="divide-y rounded-md border">
              {part.last_sales.map((sale, index) => (
                <li key={index} className="flex items-center justify-between gap-4 px-4 py-2.5 text-body-medium">
                  <span>
                    {formatDay(sale.sold_on)}
                    <span className="text-on-surface-variant"> · {sale.branch}</span>
                  </span>
                  <span className="text-end tabular-nums">
                    {t.part.sold(formatNumber(sale.quantity))}
                    {sale.unit_price !== null && (
                      <span className="block text-body-small text-on-surface-variant">{formatMoney(sale.unit_price, currency)}</span>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Section>
      </div>

      {canEdit && (
        <footer className="sticky bottom-0 border-t bg-surface-container-low p-4">
          <Button variant="filled" className="w-full" onClick={onEdit}>
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
      <h3 className="text-title-small">{title}</h3>
      {children}
    </section>
  );
}

function Line({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4 px-4 py-2.5 text-body-medium">
      <dt className={strong ? "font-medium" : "text-on-surface-variant"}>{label}</dt>
      <dd className={strong ? "font-medium tabular-nums" : "tabular-nums"}>{value}</dd>
    </div>
  );
}

function reasonText(equivalent: EquivalentPart): string {
  if (equivalent.reason_type === "oem") return t.part.equivalents.reasonOem;
  if (equivalent.reason_type === "supplier_file") return t.part.equivalents.reasonSupplierFile;
  return t.part.equivalents.reasonManual(equivalent.linked_by ?? "");
}

// One part from another brand, considered the same part: name, brand, stock per branch, price,
// and why it's considered the same. A manager can remove a wrong link; staff only sees it.
function EquivalentRow({
  partId,
  equivalent,
  canEdit,
  currency,
}: {
  partId: string;
  equivalent: EquivalentPart;
  canEdit: boolean;
  currency: string;
}) {
  return (
    <li className="grid gap-1.5 px-4 py-3 text-body-medium">
      <div className="flex items-start justify-between gap-3">
        <div className="grid min-w-0 gap-0.5">
          <p className="font-medium">{equivalent.name}</p>
          <p className="text-body-small text-on-surface-variant">
            {[equivalent.sku, equivalent.brand].filter(Boolean).join(" · ")}
          </p>
        </div>
        <div className="grid shrink-0 gap-1 text-end">
          <span className="tabular-nums">{formatMoney(equivalent.price, currency)}</span>
          <Badge variant={equivalent.in_stock ? "success" : "error"}>
            {equivalent.in_stock ? t.part.equivalents.inStock : t.part.equivalents.outOfStock}
          </Badge>
        </div>
      </div>
      <p className="text-body-small text-on-surface-variant">
        {equivalent.stock.map((row) => `${row.branch} ${formatNumber(row.quantity)}`).join(" · ")}
      </p>
      <div className="flex items-center justify-between gap-3">
        <p className="text-body-small text-on-surface-variant">{reasonText(equivalent)}</p>
        {canEdit && equivalent.link_id && <RemoveEquivalentButton partId={partId} linkId={equivalent.link_id} />}
      </div>
    </li>
  );
}

function RemoveEquivalentButton({ partId, linkId }: { partId: string; linkId: string }) {
  const removeEquivalent = useRemoveEquivalent(partId);

  function confirmed() {
    removeEquivalent.mutate(linkId, {
      onSuccess: () => toast.success(t.part.equivalents.removed),
      onError: (error) => toast.error(error.message),
    });
  }

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button size="sm" variant="text" disabled={removeEquivalent.isPending}>
          {t.common.remove}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t.part.equivalents.removeTitle}</DialogTitle>
          <DialogDescription>{t.part.equivalents.removeText}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="text">{t.common.cancel}</Button>
          </DialogClose>
          <DialogClose asChild>
            <Button variant="danger" onClick={confirmed}>
              {t.common.remove}
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// A manager links two parts by hand: search by name, SKU or OEM reference, then pick one.
function AddEquivalentButton({ part }: { part: PartDetail }) {
  const [open, setOpen] = useState(false);
  const addEquivalent = useAddEquivalent(part.id);

  function changeOpen(next: boolean) {
    addEquivalent.reset();
    setOpen(next);
  }

  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogTrigger asChild>
        <Button variant="text" size="sm" className="justify-self-start">
          <Link2Icon aria-hidden="true" />
          {t.part.equivalents.link}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t.part.equivalents.linkTitle}</DialogTitle>
          <DialogDescription>{t.part.equivalents.linkHelp}</DialogDescription>
        </DialogHeader>
        {open && <LinkPartSearch part={part} addEquivalent={addEquivalent} onLinked={() => changeOpen(false)} />}
      </DialogContent>
    </Dialog>
  );
}

function LinkPartSearch({
  part,
  addEquivalent,
  onLinked,
}: {
  part: PartDetail;
  addEquivalent: ReturnType<typeof useAddEquivalent>;
  onLinked: () => void;
}) {
  const [search, setSearch] = useState("");
  const results = useParts({ search: search.trim(), direction: "asc", page: 1 }, { enabled: search.trim() !== "" });
  const taken = new Set([part.id, ...part.equivalents.map((e) => e.part_id)]);
  const options = (results.data?.items ?? []).filter((row) => !taken.has(row.id));

  return (
    <div className="grid gap-3">
      <Input
        autoFocus
        placeholder={t.part.equivalents.searchPlaceholder}
        value={search}
        onChange={(event) => setSearch(event.target.value)}
      />
      <FormError message={addEquivalent.error?.message} />
      {search.trim() !== "" && (
        <ul className="grid max-h-72 gap-1 overflow-y-auto">
          {results.isFetching ? (
            <li className="px-1 py-2 text-body-medium text-on-surface-variant">{t.part.equivalents.searching}</li>
          ) : options.length === 0 ? (
            <li className="px-1 py-2 text-body-medium text-on-surface-variant">{t.part.equivalents.noResults}</li>
          ) : (
            options.map((row) => (
              <li key={row.id}>
                <button
                  type="button"
                  disabled={addEquivalent.isPending}
                  onClick={() =>
                    addEquivalent.mutate(row.id, {
                      onSuccess: () => {
                        toast.success(t.part.equivalents.linked(row.name));
                        onLinked();
                      },
                    })
                  }
                  className="flex w-full items-center justify-between gap-3 rounded-md px-3 py-2 text-start hover:bg-on-surface/8"
                >
                  <span className="grid min-w-0 gap-0.5">
                    <span className="truncate text-body-medium">{row.name}</span>
                    <span className="truncate text-body-small text-on-surface-variant">
                      {[row.sku, row.brand].filter(Boolean).join(" · ")}
                    </span>
                  </span>
                </button>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
