import { PrinterIcon, XIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router";
import { toast } from "sonner";

import { type PurchaseOrder, usePurchaseOrder, useReceivePurchaseOrder, useSendPurchaseOrder } from "@/api/purchaseOrders";
import { ErrorState } from "@/components/ErrorState";
import { useSignedIn } from "@/components/SignedIn";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet, SheetClose, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";
import { formatMoney, formatNumber } from "@/lib/format";

const badgeVariant = { draft: "neutral", sent: "warning", received: "success" } as const;

export function PurchaseOrderPanel({ id, canEdit, onClose }: { id: string | null; canEdit: boolean; onClose: () => void }) {
  const po = usePurchaseOrder(id);

  return (
    <Sheet open={id !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="end" className="w-full overflow-y-auto sm:max-w-lg">
        {po.isError ? (
          <>
            <SheetTitle className="sr-only">{t.orders.tabs.purchaseOrders}</SheetTitle>
            <ErrorState onRetry={() => po.refetch()} retrying={po.isFetching} />
          </>
        ) : !po.data ? (
          <div className="grid gap-4 p-6" aria-busy="true">
            <SheetTitle className="sr-only">{t.orders.tabs.purchaseOrders}</SheetTitle>
            <Skeleton className="h-7 w-2/3" />
            <Skeleton className="h-32 w-full" />
          </div>
        ) : (
          <PurchaseOrderDetails po={po.data} canEdit={canEdit} />
        )}
      </SheetContent>
    </Sheet>
  );
}

function PurchaseOrderDetails({ po, canEdit }: { po: PurchaseOrder; canEdit: boolean }) {
  const currency = useSignedIn().organization.currency;
  const send = useSendPurchaseOrder();
  const receive = useReceivePurchaseOrder();
  const [receiving, setReceiving] = useState(false);
  const [quantities, setQuantities] = useState<Record<string, string>>({});

  useEffect(() => {
    setReceiving(false);
    setQuantities(Object.fromEntries(po.lines.map((line) => [line.id, String(line.quantity - line.received_quantity)])));
  }, [po.id]);

  function markSent() {
    send.mutate(po.id, { onSuccess: () => toast.success(t.purchaseOrders.sent), onError: (error) => toast.error(error.message) });
  }

  function saveReceiving() {
    const lines = Object.fromEntries(
      Object.entries(quantities).map(([lineId, value]) => [lineId, /^\d+$/.test(value.trim()) ? Number(value.trim()) : 0]),
    );
    receive.mutate(
      { id: po.id, lines },
      {
        onSuccess: () => {
          toast.success(t.purchaseOrders.received);
          setReceiving(false);
        },
        onError: (error) => toast.error(error.message),
      },
    );
  }

  return (
    <div className="flex min-h-full flex-col">
      <header className="flex items-start gap-3 border-b p-6">
        <div className="grid min-w-0 flex-1 gap-1">
          <SheetTitle className="text-headline-small">{po.order_number}</SheetTitle>
          <p dir="auto" className="text-body-medium text-on-surface-variant">
            {po.supplier_name}
          </p>
          <div className="mt-1">
            <Badge variant={badgeVariant[po.status]}>{t.purchaseOrders.statuses[po.status]}</Badge>
          </div>
        </div>
        <SheetClose asChild>
          <Button variant="text" size="icon-sm" aria-label={t.common.close}>
            <XIcon aria-hidden="true" />
          </Button>
        </SheetClose>
      </header>

      <div className="grid flex-1 content-start gap-4 p-6">
        {receiving && <p className="text-body-small text-on-surface-variant">{t.purchaseOrders.receiveHelp}</p>}
        <ul className="divide-y rounded-md border">
          {po.lines.map((line) => (
            <li key={line.id} className="grid gap-2 p-4 sm:grid-cols-[1fr_auto] sm:items-center sm:gap-6">
              <div className="min-w-0 grid gap-0.5">
                <p dir="auto" className="font-medium">
                  {line.part_name}
                </p>
                <p className="text-body-small text-on-surface-variant">
                  <bdi dir="auto">{line.part_sku}</bdi> · <bdi dir="auto">{line.branch_name}</bdi>
                </p>
                {po.status !== "draft" && (
                  <p className="text-body-small text-on-surface-variant">
                    {t.purchaseOrders.receivedQuantity}:{" "}
                    <bdi dir="ltr">
                      {formatNumber(line.received_quantity)} / {formatNumber(line.quantity)}
                    </bdi>
                  </p>
                )}
              </div>
              <div className="flex items-center gap-3 sm:flex-col sm:items-end">
                {receiving ? (
                  <Input
                    type="text"
                    inputMode="numeric"
                    aria-label={`${t.purchaseOrders.receivedQuantity} ${line.part_name}`}
                    value={quantities[line.id] ?? ""}
                    onChange={(event) => setQuantities({ ...quantities, [line.id]: event.target.value })}
                    className="h-10 w-20 text-end"
                  />
                ) : (
                  <span className="tabular-nums">{formatNumber(line.quantity)}</span>
                )}
                {line.line_cost !== undefined && (
                  <span className="tabular-nums text-on-surface-variant">{formatMoney(line.line_cost, currency)}</span>
                )}
              </div>
            </li>
          ))}
        </ul>
        {po.total_cost !== undefined && <p className="text-end text-title-medium">{formatMoney(po.total_cost, currency)}</p>}
      </div>

      <footer className="sticky bottom-0 grid gap-2 border-t bg-surface-container-low p-4">
        <Button variant="outlined" asChild>
          <Link to={`/orders/purchase-orders/${po.id}/print`} target="_blank" rel="noopener">
            <PrinterIcon aria-hidden="true" />
            {t.purchaseOrders.printOrSavePdf}
          </Link>
        </Button>
        {canEdit && po.status === "draft" && (
          <Button variant="filled" loading={send.isPending} onClick={markSent}>
            {t.purchaseOrders.markSent}
          </Button>
        )}
        {canEdit && po.status === "sent" && !receiving && (
          <Button variant="filled" onClick={() => setReceiving(true)}>
            {t.purchaseOrders.receive}
          </Button>
        )}
        {canEdit && po.status === "sent" && receiving && (
          <div className="grid grid-cols-2 gap-2">
            <Button variant="outlined" onClick={() => setReceiving(false)}>
              {t.common.cancel}
            </Button>
            <Button variant="filled" loading={receive.isPending} onClick={saveReceiving}>
              {t.purchaseOrders.receiveSave}
            </Button>
          </div>
        )}
      </footer>
    </div>
  );
}
