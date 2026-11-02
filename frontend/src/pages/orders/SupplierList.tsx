import { ChevronRightIcon } from "lucide-react";

import type { OrderGroup } from "@/api/orders";
import { useSignedIn } from "@/components/SignedIn";
import { Card } from "@/components/ui/card";
import { t } from "@/i18n";
import { formatMoney, formatNumber } from "@/lib/format";

export function groupName(group: OrderGroup): string {
  if (group.key === "didnt_fit") return t.orders.didntFitBudget;
  return group.supplier_name ?? t.orders.noSupplierGroup;
}

// One row per supplier with its total: open one to see its lines.
export function SupplierList({ groups, onOpen }: { groups: OrderGroup[]; onOpen: (key: string) => void }) {
  const currency = useSignedIn().organization.currency;

  return (
    <Card className="py-0">
      <ul className="divide-y">
        {groups.map((group) => (
          <li key={group.key}>
            <button
              type="button"
              onClick={() => onOpen(group.key)}
              className="flex w-full items-center justify-between gap-4 px-6 py-4 text-start transition-colors hover:bg-on-surface/8 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-primary"
            >
              <span className="grid min-w-0">
                <span dir="auto" className="truncate text-title-medium">
                  {groupName(group)}
                </span>
                <span className="text-body-small text-on-surface-variant">
                  {t.orders.groupLines(group.line_count, formatNumber(group.line_count), formatNumber(group.pending_count))}
                </span>
              </span>
              <span className="flex shrink-0 items-center gap-2">
                <span className="text-body-large tabular-nums">{formatMoney(group.total_cost, currency)}</span>
                <ChevronRightIcon aria-hidden="true" className="size-5 text-on-surface-variant rtl:rotate-180" />
              </span>
            </button>
          </li>
        ))}
      </ul>
    </Card>
  );
}
