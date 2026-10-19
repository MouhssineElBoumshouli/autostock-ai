import { FileTextIcon } from "lucide-react";
import { useState } from "react";

import { type PurchaseOrderSummary, type PurchaseOrderStatus, usePurchaseOrders } from "@/api/purchaseOrders";
import { type Column, DataTable } from "@/components/DataTable";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { useSignedIn } from "@/components/SignedIn";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { t } from "@/i18n";
import { formatDay, formatMoney, formatNumber } from "@/lib/format";

import { PurchaseOrderPanel } from "./PurchaseOrderPanel";

const badgeVariant = { draft: "neutral", sent: "warning", received: "success" } as const satisfies Record<
  PurchaseOrderStatus,
  "neutral" | "warning" | "success"
>;

export function PurchaseOrdersTab({ canEdit }: { canEdit: boolean }) {
  const currency = useSignedIn().organization.currency;
  const orders = usePurchaseOrders();
  const [openId, setOpenId] = useState<string | null>(null);

  const columns: Column<PurchaseOrderSummary>[] = [
    { header: t.purchaseOrders.columns.orderNumber, primary: true, cell: (po) => po.order_number },
    { header: t.purchaseOrders.columns.supplier, cell: (po) => po.supplier_name },
    { header: t.purchaseOrders.columns.status, cell: (po) => <Badge variant={badgeVariant[po.status]}>{t.purchaseOrders.statuses[po.status]}</Badge> },
    { header: t.purchaseOrders.columns.lines, align: "end", cell: (po) => formatNumber(po.line_count) },
    { header: t.purchaseOrders.columns.total, align: "end", cell: (po) => formatMoney(po.total_cost, currency) },
    { header: t.purchaseOrders.columns.date, cell: (po) => formatDay(po.created_at.slice(0, 10)) },
  ];

  return (
    <div className="grid gap-4">
      <Card className="py-0">
        {orders.isError ? (
          <ErrorState onRetry={() => orders.refetch()} retrying={orders.isFetching} />
        ) : orders.data?.length === 0 ? (
          <EmptyState icon={FileTextIcon} title={t.purchaseOrders.emptyTitle} description={t.purchaseOrders.emptyText} />
        ) : (
          <DataTable
            columns={columns}
            rows={orders.data ?? []}
            rowKey={(po) => po.id}
            loading={orders.isPending}
            onRowClick={(po) => setOpenId(po.id)}
          />
        )}
      </Card>
      <PurchaseOrderPanel id={openId} canEdit={canEdit} onClose={() => setOpenId(null)} />
    </div>
  );
}
