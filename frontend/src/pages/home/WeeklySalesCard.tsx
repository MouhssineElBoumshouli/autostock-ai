import { TrendingUpIcon } from "lucide-react";

import type { WeeklySales } from "@/api/today";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { t } from "@/i18n";
import { formatNumber } from "@/lib/format";

import { WeeklySalesChart } from "./WeeklySalesChart";

export function WeeklySalesCard({ sales }: { sales: WeeklySales | null }) {
  return (
    <Card className="gap-4 pb-2">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <TrendingUpIcon aria-hidden="true" className="size-5 text-on-surface-variant" />
          {t.home.weeklySales.title}
        </CardTitle>
      </CardHeader>
      {sales === null ? (
        <CardContent>
          <p className="text-body-medium text-on-surface-variant">{t.home.weeklySales.noSalesYet}</p>
        </CardContent>
      ) : (
        <>
          <CardContent className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <p className="text-headline-small tabular-nums sm:text-display-small">{formatNumber(sales.this_week)}</p>
            <p className="text-body-medium text-on-surface-variant">{t.home.weeklySales.normalWeek(formatNumber(sales.normal))}</p>
          </CardContent>
          <CardContent>
            <WeeklySalesChart weeks={sales.weeks} normal={sales.normal} />
          </CardContent>
          {sales.top_parts.length > 0 && (
            <div className="grid gap-2 border-t px-6 pt-4 pb-4">
              <p className="text-label-large text-on-surface-variant">{t.home.weeklySales.topParts}</p>
              <ul className="grid gap-1">
                {sales.top_parts.map((part) => (
                  <li key={part.part_id} className="min-w-0 flex items-center justify-between gap-4 text-body-medium">
                    <span className="min-w-0 truncate">
                      {part.name} <span className="text-on-surface-variant">{part.sku}</span>
                    </span>
                    <span className="shrink-0 tabular-nums">{formatNumber(part.quantity)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </Card>
  );
}
