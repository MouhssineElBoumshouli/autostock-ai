import { ArrowLeftIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { type OrderGroup, useApproveAllForSupplier, useRunLines } from "@/api/orders";
import { ErrorState } from "@/components/ErrorState";
import { Pagination } from "@/components/Pagination";
import { useSignedIn } from "@/components/SignedIn";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";
import { formatMoney } from "@/lib/format";

import { OrderLineRow } from "./OrderLineRow";
import { groupName } from "./SupplierList";

// One supplier's lines, most urgent first, 50 at a time.
export function SupplierSection({
  runId,
  group,
  canEdit,
  onBack,
}: {
  runId: string;
  group: OrderGroup;
  canEdit: boolean;
  onBack: () => void;
}) {
  const currency = useSignedIn().organization.currency;
  const [page, setPage] = useState(1);
  const lines = useRunLines(runId, group.key, page);
  const approveAll = useApproveAllForSupplier();
  const supplierId = group.supplier_id;

  function approveAllForSupplier() {
    if (!supplierId) return;
    approveAll.mutate(
      { runId, supplierId },
      {
        onSuccess: ({ approved }) => toast.success(t.orders.approvedAll(String(approved))),
        onError: (error) => toast.error(error.message),
      },
    );
  }

  return (
    <div className="grid gap-4">
      <Button variant="text" className="justify-self-start" onClick={onBack}>
        <ArrowLeftIcon aria-hidden="true" className="rtl:rotate-180" />
        {t.orders.allSuppliers}
      </Button>
      <Card className="py-0">
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b py-4">
          <CardTitle dir="auto">{groupName(group)}</CardTitle>
          <div className="flex flex-wrap items-center gap-3">
            {group.total_cost !== undefined && (
              <span className="tabular-nums text-body-medium text-on-surface-variant">
                {t.orders.supplierTotal(formatMoney(group.total_cost, currency))}
              </span>
            )}
            {canEdit && supplierId && group.pending_count > 1 && (
              <Button size="sm" variant="tonal" disabled={approveAll.isPending} onClick={approveAllForSupplier}>
                {t.orders.approveAllForSupplier}
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {lines.isError ? (
            <ErrorState onRetry={() => lines.refetch()} retrying={lines.isFetching} />
          ) : !lines.data ? (
            <div className="grid gap-3 p-4" aria-busy="true">
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-20 w-full" />
            </div>
          ) : (
            <>
              <ul className="divide-y">
                {lines.data.items.map((line) => (
                  <OrderLineRow key={line.id} line={line} canEdit={canEdit} />
                ))}
              </ul>
              {lines.data.total > lines.data.page_size && (
                <Pagination
                  page={lines.data.page}
                  pageSize={lines.data.page_size}
                  total={lines.data.total}
                  shown={lines.data.items.length}
                  onPage={setPage}
                />
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
