import { PackageIcon, ReplaceIcon, UploadIcon } from "lucide-react";
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
import { formatNumber, isolate } from "@/lib/format";

import { ForecastStatusBar } from "./ForecastStatusBar";
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
    running_out: params.get("running_out") === "true" ? true : undefined,
    // While searching, the best match comes first unless a column was picked.
    sort: (params.get("sort") as SortKey | null) ?? (params.get("search") ? undefined : "name"),
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
        <span className="block max-w-48 xl:max-w-72">
          <span dir="auto" className="block truncate font-medium">
            {part.name}
          </span>
          {part.equivalent_note && (
            <span className="mt-0.5 flex items-center gap-1 text-body-small font-medium text-primary">
              <ReplaceIcon aria-hidden="true" className="size-3.5 shrink-0" />
              <span className="truncate">
                {t.stock.outOfStockEquivalent(formatNumber(part.equivalent_note.quantity), isolate(part.equivalent_note.brand))}
              </span>
            </span>
          )}
        </span>
      ),
    },
    {
      header: t.stock.columns.sku,
      sortKey: "sku",
      className: "hidden lg:table-cell",
      cell: (part) => (
        <span dir="auto" className="text-on-surface-variant">
          {part.sku}
        </span>
      ),
    },
    {
      header: t.stock.columns.brand,
      sortKey: "brand",
      className: "hidden 2xl:table-cell",
      cell: (part) => <bdi dir="auto">{part.brand ?? "—"}</bdi>,
    },
    { header: t.stock.columns.inStock, sortKey: "quantity", align: "end", cell: (part) => formatNumber(part.quantity) },
    {
      header: t.stock.columns.minimum,
      sortKey: "min_stock",
      align: "end",
      className: "hidden 2xl:table-cell",
      cell: (part) => formatNumber(part.min_stock),
    },
    {
      header: t.stock.columns.status,
      sortKey: "status",
      cell: (part) => (
        <span className="grid gap-0.5">
          <StockBadge status={part.status} />
          {part.zero_branch_name && (
            <span className="text-body-small text-error">{t.stock.zeroBranchNote(part.zero_branch_name)}</span>
          )}
        </span>
      ),
    },
    {
      header: t.stock.columns.supplier,
      sortKey: "supplier",
      className: "hidden 2xl:table-cell",
      cell: (part) => <bdi dir="auto">{part.supplier ?? "—"}</bdi>,
    },
    {
      header: t.stock.columns.next30Days,
      sortKey: "expected_30d",
      align: "end",
      className: "hidden xl:table-cell",
      cell: (part) => formatNumber(part.expected_30d),
    },
    { header: t.stock.columns.runsOutIn, sortKey: "runs_out_days", cell: (part) => runsOutLabel(part) },
  ];

  const filtered = Boolean(
    query.search || query.status || query.category || query.branch || query.supplier || query.running_out,
  );
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
      <div className="grid grid-cols-1 gap-8">
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
    <div className="grid grid-cols-1 gap-8">
      <PageHeader title={t.nav.stock} subtitle={t.stock.subtitle} action={importButton} />
      <ForecastStatusBar />
      <StockStats
        summary={summary.data}
        loading={summary.isPending}
        activeStatus={query.status}
        onFilter={(status) => update({ status })}
        runningOut={query.running_out}
        onToggleRunningOut={(value) => update({ running_out: value ? "true" : undefined })}
      />
      <div className="grid min-w-0 gap-4">
        <StockFilters values={{ ...query, search: query.search ?? "" }} onChange={update} />
        <Card className="min-w-0 py-0">
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
              {parts.data?.closest && <p className="text-body-medium text-on-surface-variant">{t.stock.closestParts}</p>}
              <DataTable
                columns={columns}
                rows={parts.data?.items ?? []}
                rowKey={(part) => part.id}
                loading={parts.isPending}
                sort={query.sort && { key: query.sort, direction: query.direction }}
                onSort={(sort) => update({ sort: sort.key, direction: sort.direction })}
                onRowClick={(part) => update({ part: part.id }, true)}
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
      <PartPanel partId={openPart} canEdit={canEdit} branch={query.branch} onClose={() => update({ part: undefined }, true)} />
    </div>
  );
}

function runsOutLabel(part: PartRow): string {
  if (part.status === "out") return t.stock.runsOut.alreadyOut;
  if (part.runs_out_days === null) return t.stock.runsOut.overSixty;
  return t.stock.runsOut.aboutDays(t.common.days(part.runs_out_days, formatNumber(part.runs_out_days)));
}
