import { ClipboardListIcon } from "lucide-react";
import { useSearchParams } from "react-router";

import { useCreateSuggestions, useLatestRun } from "@/api/orders";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";
import { formatDateTime } from "@/lib/format";

import { BudgetBar } from "./BudgetBar";
import { SupplierList } from "./SupplierList";
import { SupplierSection } from "./SupplierSection";

// The suppliers to order from, with their totals; one opens to show its lines (?supplier=).
export function WhatToOrderTab({ canEdit }: { canEdit: boolean }) {
  const run = useLatestRun();
  const create = useCreateSuggestions();
  const [params, setParams] = useSearchParams();

  function openGroup(key: string | null) {
    const next = new URLSearchParams(params);
    if (key) next.set("supplier", key);
    else next.delete("supplier");
    setParams(next);
  }

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
  const opened = data?.groups.find((group) => group.key === params.get("supplier"));

  if (data && opened) {
    return <SupplierSection key={`${data.id}-${opened.key}`} runId={data.id} group={opened} canEdit={canEdit} onBack={() => openGroup(null)} />;
  }

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
      ) : data.groups.length === 0 ? (
        <Card className="py-0">
          <EmptyState icon={ClipboardListIcon} title={t.orders.emptyTitle} description={t.orders.emptyText} />
        </Card>
      ) : (
        <SupplierList groups={data.groups} onOpen={openGroup} />
      )}
    </div>
  );
}
