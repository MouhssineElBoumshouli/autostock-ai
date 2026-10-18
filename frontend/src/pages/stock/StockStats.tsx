import { BoxIcon, CircleCheckIcon, PackageXIcon, TriangleAlertIcon } from "lucide-react";

import type { StockSummary } from "@/api/stock";
import { StatCard } from "@/components/StatCard";
import { t } from "@/i18n";
import { formatNumber } from "@/lib/format";

// The four numbers on top of Stock and Home. Only real counts from the database.
export function StockStats({ summary, loading }: { summary?: StockSummary; loading: boolean }) {
  const value = (n: number | undefined) => formatNumber(n ?? 0);

  return (
    <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
      <StatCard icon={BoxIcon} label={t.stock.stats.all} value={value(summary?.all)} note={t.stock.stats.allNote} loading={loading} />
      <StatCard
        icon={CircleCheckIcon}
        tone="success"
        label={t.stock.healthy}
        value={value(summary?.healthy)}
        note={t.stock.stats.healthyNote}
        loading={loading}
      />
      <StatCard
        icon={TriangleAlertIcon}
        tone="warning"
        label={t.stock.low}
        value={value(summary?.low)}
        note={t.stock.stats.lowNote}
        loading={loading}
      />
      <StatCard
        icon={PackageXIcon}
        tone="destructive"
        label={t.stock.out}
        value={value(summary?.out)}
        note={t.stock.stats.outNote}
        loading={loading}
      />
    </div>
  );
}
