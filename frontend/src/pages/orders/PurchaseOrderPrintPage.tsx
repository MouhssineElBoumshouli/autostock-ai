import { PrinterIcon } from "lucide-react";
import { useEffect } from "react";
import { useParams } from "react-router";

import { usePurchaseOrder } from "@/api/purchaseOrders";
import { ErrorState } from "@/components/ErrorState";
import { useSignedIn } from "@/components/SignedIn";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";
import { formatDay, formatMoney, formatNumber } from "@/lib/format";

// A clean page for one purchase order: shop name, supplier, date, lines, totals.
// "Download PDF" opens the browser's print dialog ("Save as PDF" is one of its options).
// No sidebar or top bar here (see router.tsx), so what prints is only this.
export function PurchaseOrderPrintPage() {
  const { id = null } = useParams();
  const me = useSignedIn();
  const po = usePurchaseOrder(id);

  useEffect(() => {
    document.title = po.data ? `${po.data.order_number} · ${t.appName}` : t.appName;
  }, [po.data]);

  if (po.isError) {
    return (
      <div className="mx-auto max-w-2xl p-8">
        <ErrorState onRetry={() => po.refetch()} retrying={po.isFetching} />
      </div>
    );
  }

  if (!po.data) {
    return (
      <div className="mx-auto grid max-w-2xl gap-4 p-8" aria-busy="true">
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const order = po.data;

  return (
    <div className="mx-auto max-w-2xl p-6 sm:p-10">
      <div className="mb-6 flex justify-end print:hidden">
        <Button variant="filled" onClick={() => window.print()}>
          <PrinterIcon aria-hidden="true" />
          {t.purchaseOrders.downloadPdf}
        </Button>
      </div>

      <header className="mb-8 flex items-start justify-between gap-4 border-b border-black/20 pb-6">
        <div>
          <p className="text-headline-small font-medium">{me.organization.name}</p>
          <p className="mt-1 text-body-medium">{t.purchaseOrders.print.orderNumber}: {order.order_number}</p>
          <p className="text-body-medium">
            {t.purchaseOrders.print.date}: {formatDay(order.created_at.slice(0, 10))}
          </p>
        </div>
        <div className="text-end">
          <p className="text-title-medium">{t.purchaseOrders.print.supplier}</p>
          <p dir="auto" className="text-body-medium">
            {order.supplier_name}
          </p>
          {order.supplier_phone && <p className="text-body-medium">{order.supplier_phone}</p>}
          {order.supplier_email && <p className="text-body-medium">{order.supplier_email}</p>}
        </div>
      </header>

      <table className="w-full border-collapse text-body-medium">
        <thead>
          <tr className="border-b border-black/40 text-start">
            <th className="py-2 pe-3 text-start font-medium">{t.purchaseOrders.print.part}</th>
            <th className="px-3 py-2 text-start font-medium">{t.purchaseOrders.print.sku}</th>
            <th className="px-3 py-2 text-start font-medium">{t.purchaseOrders.print.branch}</th>
            <th className="px-3 py-2 text-end font-medium">{t.purchaseOrders.print.quantity}</th>
            <th className="px-3 py-2 text-end font-medium">{t.purchaseOrders.print.unitCost}</th>
            <th className="ps-3 py-2 text-end font-medium">{t.purchaseOrders.print.total}</th>
          </tr>
        </thead>
        <tbody>
          {order.lines.map((line) => (
            <tr key={line.id} className="border-b border-black/10">
              <td className="py-2 pe-3">
                <bdi dir="auto">{line.part_name}</bdi>
              </td>
              <td className="px-3 py-2">
                <bdi dir="auto">{line.part_sku}</bdi>
              </td>
              <td className="px-3 py-2">{line.branch_name}</td>
              <td className="px-3 py-2 text-end tabular-nums">{formatNumber(line.quantity)}</td>
              <td className="px-3 py-2 text-end tabular-nums">{formatMoney(line.unit_cost, me.organization.currency)}</td>
              <td className="ps-3 py-2 text-end tabular-nums">{formatMoney(line.line_cost, me.organization.currency)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="mt-4 flex justify-end border-t border-black/40 pt-4">
        <p className="text-title-medium">
          {t.purchaseOrders.print.total}: {formatMoney(order.total_cost, me.organization.currency)}
        </p>
      </div>
    </div>
  );
}
