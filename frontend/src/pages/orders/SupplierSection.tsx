import { toast } from "sonner";

import { type OrderLine, useApproveAllForSupplier } from "@/api/orders";
import { useSignedIn } from "@/components/SignedIn";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { t } from "@/i18n";
import { formatMoney } from "@/lib/format";

import { lineCost, OrderLineRow } from "./OrderLineRow";

// One supplier's lines, in the order the suggestions came back (most urgent first).
export function SupplierSection({
  runId,
  supplierId,
  supplierName,
  lines,
  canEdit,
}: {
  runId: string;
  supplierId: string | null;
  supplierName: string | null;
  lines: OrderLine[];
  canEdit: boolean;
}) {
  const currency = useSignedIn().organization.currency;
  const approveAll = useApproveAllForSupplier();
  const total = lines.reduce((sum, line) => sum + lineCost(line), 0);
  const pending = lines.filter((line) => line.status === "suggested" || line.status === "cut_by_budget");

  function approveAllForSupplier() {
    if (!supplierId) return;
    approveAll.mutate(
      { runId, supplierId },
      {
        onSuccess: (approved) => toast.success(t.orders.approvedAll(String(approved.length))),
        onError: (error) => toast.error(error.message),
      },
    );
  }

  return (
    <Card className="py-0">
      <CardHeader className="flex-row items-center justify-between gap-4 border-b py-4">
        <CardTitle>{supplierName ?? t.orders.noSupplierGroup}</CardTitle>
        <div className="flex shrink-0 items-center gap-3">
          <span className="tabular-nums text-body-medium text-on-surface-variant">{t.orders.supplierTotal(formatMoney(total, currency))}</span>
          {canEdit && supplierId && pending.length > 1 && (
            <Button size="sm" variant="tonal" disabled={approveAll.isPending} onClick={approveAllForSupplier}>
              {t.orders.approveAllForSupplier}
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <ul className="divide-y">
          {lines.map((line) => (
            <OrderLineRow key={line.id} line={line} canEdit={canEdit} />
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
