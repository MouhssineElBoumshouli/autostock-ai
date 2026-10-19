import { ClipboardListIcon } from "lucide-react";

import { type OrderLine, useCreateSuggestions, useLatestRun } from "@/api/orders";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";
import { formatDateTime } from "@/lib/format";

import { BudgetBar } from "./BudgetBar";
import { SupplierSection } from "./SupplierSection";

type SupplierGroup = { supplierId: string | null; supplierName: string | null; lines: OrderLine[] };

// Groups kept lines by supplier, in the order suggestions came back (most urgent first).
// Lines still cut by the budget are pulled out into their own section, across suppliers.
function group(lines: OrderLine[]): { groups: SupplierGroup[]; didntFit: OrderLine[] } {
  const didntFit = lines.filter((line) => line.status === "cut_by_budget");
  const groups: SupplierGroup[] = [];
  const index = new Map<string, SupplierGroup>();
  for (const line of lines) {
    if (line.status === "cut_by_budget") continue;
    const key = line.supplier_id ?? "none";
    let found = index.get(key);
    if (!found) {
      found = { supplierId: line.supplier_id, supplierName: line.supplier_name, lines: [] };
      index.set(key, found);
      groups.push(found);
    }
    found.lines.push(line);
  }
  return { groups, didntFit };
}

export function WhatToOrderTab({ canEdit }: { canEdit: boolean }) {
  const run = useLatestRun();
  const create = useCreateSuggestions();

  if (run.isError) {
    return (
      <Card className="py-0">
        <ErrorState onRetry={() => run.refetch()} retrying={run.isFetching} />
      </Card>
    );
  }

  if (run.isPending) {
    return (
      <div className="grid gap-4" aria-busy="true">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const data = run.data;
  const { groups, didntFit } = data ? group(data.lines) : { groups: [], didntFit: [] };

  return (
    <div className="grid gap-4">
      {canEdit && (
        <BudgetBar
          run={data}
          loading={create.isPending}
          onRun={(budget) => create.mutate(budget)}
        />
      )}
      {data?.history_last_day && (
        <p className="text-body-small text-on-surface-variant">{t.orders.lastRun(formatDateTime(data.created_at))}</p>
      )}

      {!data ? (
        <Card className="py-0">
          <EmptyState icon={ClipboardListIcon} title={t.orders.noRunYet} />
        </Card>
      ) : groups.length === 0 && didntFit.length === 0 ? (
        <Card className="py-0">
          <EmptyState icon={ClipboardListIcon} title={t.orders.emptyTitle} description={t.orders.emptyText} />
        </Card>
      ) : (
        <>
          {groups.map((group) => (
            <SupplierSection
              key={group.supplierId ?? "none"}
              runId={data.id}
              supplierId={group.supplierId}
              supplierName={group.supplierName}
              lines={group.lines}
              canEdit={canEdit}
            />
          ))}
          {didntFit.length > 0 && (
            <SupplierSection
              runId={data.id}
              supplierId={null}
              supplierName={t.orders.didntFitBudget}
              lines={didntFit}
              canEdit={canEdit}
            />
          )}
        </>
      )}
    </div>
  );
}
