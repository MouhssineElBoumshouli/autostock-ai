import { PackageIcon, UploadIcon } from "lucide-react";
import { useCallback } from "react";
import { Link, useSearchParams } from "react-router";

import { type PartRow, type SortKey, type StatusFilter, useParts, useStockSummary } from "@/api/stock";
import { type Column, DataTable } from "@/components/DataTable";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { PageHeader } from "@/components/PageHeader";
import { Pagination } from "@/components/Pagination";
import { useSignedIn } from "@/components/SignedIn";
import { StockBadge } from "@/components/StockBadge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { t } from "@/i18n";
import { formatNumber } from "@/lib/format";

import { PartPanel } from "./PartPanel";
import { StockFilters } from "./StockFilters";
import { StockStats } from "./StockStats";

// Everything is kept in the address (?search=…&status=low&part=…), so links and the back button work.
export function StockPage() {
  const [params, setParams] = useSearchParams();
  const canEdit = useSignedIn().user.role !== "staff";
  const summary = useStockSummary();
  const query = {
    search: params.get("search") ?? undefined,
    status: (params.get("status") as StatusFilter | null) ?? undefined,
    category: params.get("category") ?? undefined,
    branch: params.get("branch") ?? undefined,
    supplier: params.get("supplier") ?? undefined,
    sort: (params.get("sort") as SortKey | null) ?? "name",
    direction: params.get("direction") === "desc" ? ("desc" as const) : ("asc" as const),
    page: Math.max(1, Number(params.get("page")) || 1),
  };
  const parts = useParts(query);
  const openPart = params.get("part");

  const update = useCallback(
    (changes: Record<string, string | undefined>, keepPage = false) => {
      setParams((current) => {
        const next = new URLSearchParams(current);
        for (const [key, value] of Object.entries(changes)) {
          if (value) next.set(key, value);
          else next.delete(key);
        }
        if (!keepPage) next.delete("page");
        return next;
      });
    },
    [setParams],
  );

  const columns: Column<PartRow>[] = [
    {
      header: t.stock.columns.part,
      primary: true,
      sortKey: "name",
      cell: (part) => (
        <button
          type="button"
          onClick={() => update({ part: part.id }, true)}
          aria-label={t.part.openDetails(part.name)}
          className="max-w-72 truncate text-start font-medium hover:text-primary hover:underline"
        >
          {part.name}
        </button>
      ),
    },
    { header: t.stock.columns.sku, sortKey: "sku", cell: (part) => <span className="text-on-surface-variant">{part.sku}</span> },
    { header: t.stock.columns.brand, sortKey: "brand", cell: (part) => part.brand ?? "—" },
    { header: t.stock.columns.inStock, sortKey: "quantity", align: "end", cell: (part) => formatNumber(part.quantity) },
    { header: t.stock.columns.minimum, sortKey: "min_stock", align: "end", cell: (part) => formatNumber(part.min_stock) },
    { header: t.stock.columns.status, sortKey: "status", cell: (part) => <StockBadge status={part.status} /> },
    { header: t.stock.columns.supplier, sortKey: "supplier", cell: (part) => part.supplier ?? "—" },
  ];

  const filtered = Boolean(query.search || query.status || query.category || query.branch || query.supplier);
  const noPartsAtAll = summary.data !== undefined && summary.data.all === 0 && parts.data?.total === 0 && !filtered;
  const importButton = canEdit && (
    <Button variant="filled" asChild>
      <Link to="/stock/import">
        <UploadIcon aria-hidden="true" />
        {t.stock.importButton}
      </Link>
    </Button>
  );

  if (noPartsAtAll) {
    return (
      <div className="grid gap-8">
        <PageHeader title={t.nav.stock} subtitle={t.stock.subtitle} />
        <Card className="py-0">
          <EmptyState
            icon={PackageIcon}
            title={t.stock.emptyTitle}
            description={canEdit ? t.stock.emptyText : t.stock.emptyStaff}
            action={importButton}
          />
        </Card>
      </div>
    );
  }

  return (
    <div className="grid gap-8">
      <PageHeader title={t.nav.stock} subtitle={t.stock.subtitle} action={importButton} />
      <StockStats summary={summary.data} loading={summary.isPending} />
      <div className="grid gap-4">
        <StockFilters values={{ ...query, search: query.search ?? "" }} onChange={update} />
        <Card className="py-0">
          {parts.isError ? (
            <ErrorState onRetry={() => parts.refetch()} retrying={parts.isFetching} />
          ) : parts.data?.total === 0 ? (
            <EmptyState
              icon={PackageIcon}
              title={t.stock.noMatch}
              action={<Button onClick={() => setParams(new URLSearchParams())}>{t.common.clearFilters}</Button>}
            />
          ) : (
            <>
              <DataTable
                columns={columns}
                rows={parts.data?.items ?? []}
                rowKey={(part) => part.id}
                loading={parts.isPending}
                sort={{ key: query.sort, direction: query.direction }}
                onSort={(sort) => update({ sort: sort.key, direction: sort.direction })}
              />
              {parts.data && (
                <Pagination
                  page={parts.data.page}
                  pageSize={parts.data.page_size}
                  total={parts.data.total}
                  shown={parts.data.items.length}
                  onPage={(page) => update({ page: String(page) }, true)}
                />
              )}
            </>
          )}
        </Card>
      </div>
      <PartPanel partId={openPart} canEdit={canEdit} onClose={() => update({ part: undefined }, true)} />
    </div>
  );
}
