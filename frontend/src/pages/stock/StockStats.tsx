import { BoxIcon, CircleCheckIcon, PackageXIcon, TriangleAlertIcon } from "lucide-react";

import type { StatusFilter, StockSummary } from "@/api/stock";
import { StatCard } from "@/components/StatCard";
import { t } from "@/i18n";
import { formatNumber } from "@/lib/format";

// The four numbers on top of Stock and Home. Only real counts from the database.
// On the Stock screen (onFilter given) tapping one filters the list; tapping it again clears it.
export function StockStats({
  summary,
  loading,
  activeStatus,
  onFilter,
}: {
  summary?: StockSummary;
  loading: boolean;
  activeStatus?: StatusFilter;
  onFilter?: (status: StatusFilter | undefined) => void;
}) {
  const value = (n: number | undefined) => formatNumber(n ?? 0);

  function toggle(status: StatusFilter) {
    onFilter?.(activeStatus === status ? undefined : status);
  }

  return (
    <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
      <StatCard
        icon={BoxIcon}
        label={t.stock.stats.all}
        value={value(summary?.all)}
        note={t.stock.stats.allNote}
        loading={loading}
        active={onFilter !== undefined && activeStatus === undefined}
        onClick={onFilter && (() => onFilter(undefined))}
      />
      <StatCard
        icon={CircleCheckIcon}
        tone="success"
        label={t.stock.healthy}
        value={value(summary?.healthy)}
        note={t.stock.stats.healthyNote}
        loading={loading}
        active={activeStatus === "healthy"}
        onClick={onFilter && (() => toggle("healthy"))}
      />
      <StatCard
        icon={TriangleAlertIcon}
        tone="warning"
        label={t.stock.low}
        value={value(summary?.low)}
        note={t.stock.stats.lowNote}
        loading={loading}
        active={activeStatus === "low"}
        onClick={onFilter && (() => toggle("low"))}
      />
      <StatCard
        icon={PackageXIcon}
        tone="error"
        label={t.stock.out}
        value={value(summary?.out)}
        note={t.stock.stats.outNote}
        loading={loading}
        active={activeStatus === "out"}
        onClick={onFilter && (() => toggle("out"))}
      />
    </div>
  );
}
