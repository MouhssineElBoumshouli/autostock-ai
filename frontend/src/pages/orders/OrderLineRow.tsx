import { useState } from "react";
import { toast } from "sonner";

import { type OrderLine, useDecideLine } from "@/api/orders";
import { useSignedIn } from "@/components/SignedIn";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { t } from "@/i18n";
import { formatMoney, formatNumber } from "@/lib/format";
import { orderReason } from "@/lib/orderReason";

function wholeNumber(text: string): number | "invalid" {
  return /^\d+$/.test(text.trim()) && Number(text.trim()) > 0 ? Number(text.trim()) : "invalid";
}

const badgeVariant = {
  suggested: "neutral",
  cut_by_budget: "warning",
  approved: "success",
  rejected: "error",
} as const;

export function lineCost(line: OrderLine): number {
  return (line.approved_quantity ?? line.quantity) * (line.unit_cost ?? 0);
}

// One part, for one branch: the suggested quantity (editable), its cost, why, and the decision.
export function OrderLineRow({ line, canEdit }: { line: OrderLine; canEdit: boolean }) {
  const currency = useSignedIn().organization.currency;
  const decide = useDecideLine();
  const [quantity, setQuantity] = useState(String(line.approved_quantity ?? line.quantity));
  const [showError, setShowError] = useState(false);
  const parsed = wholeNumber(quantity);

  function approve() {
    if (parsed === "invalid") {
      setShowError(true);
      return;
    }
    decide.mutate(
      { id: line.id, decision: "approve", quantity: parsed },
      { onSuccess: () => toast.success(t.orders.approved), onError: (error) => toast.error(error.message) },
    );
  }

  function reject() {
    decide.mutate(
      { id: line.id, decision: "reject" },
      { onSuccess: () => toast.success(t.orders.rejected), onError: (error) => toast.error(error.message) },
    );
  }

  return (
    <li className="grid gap-3 p-4 sm:grid-cols-[1fr_auto] sm:items-center sm:gap-6">
      <div className="min-w-0 grid gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <p dir="auto" className="font-medium">
            {line.part_name}
          </p>
          <Badge variant={badgeVariant[line.status]}>{t.orders.statuses[line.status]}</Badge>
        </div>
        <p className="text-body-small text-on-surface-variant">
          <bdi dir="auto">{line.part_sku}</bdi> · <bdi dir="auto">{line.branch_name}</bdi> · {t.orders.columns.inStock} {formatNumber(line.on_hand)}
        </p>
        <p className="text-body-small text-on-surface-variant">{orderReason(line)}</p>
        {!line.supplier_id && <p className="text-body-small text-error">{t.orders.noSupplier}</p>}
      </div>

      <div className="flex flex-wrap items-center gap-3 sm:flex-col sm:items-end">
        <div className="flex items-center gap-3">
          {canEdit ? (
            <Input
              type="text"
              inputMode="numeric"
              value={quantity}
              aria-label={t.orders.editQuantity}
              aria-invalid={showError && parsed === "invalid" ? true : undefined}
              onChange={(event) => {
                setQuantity(event.target.value);
                setShowError(false);
              }}
              className="h-10 w-20 text-end"
            />
          ) : (
            <span className="tabular-nums">{formatNumber(line.approved_quantity ?? line.quantity)}</span>
          )}
          <span className="tabular-nums text-on-surface-variant">{formatMoney(lineCost(line), currency)}</span>
        </div>
        {showError && parsed === "invalid" && <p className="text-body-small text-error">{t.orders.quantityError}</p>}
        {canEdit && (
          <div className="flex gap-2">
            <Button size="sm" variant="outlined" disabled={decide.isPending} onClick={reject}>
              {t.orders.reject}
            </Button>
            <Button size="sm" variant="tonal" disabled={!line.supplier_id || decide.isPending} onClick={approve}>
              {t.orders.approve}
            </Button>
          </div>
        )}
      </div>
    </li>
  );
}
