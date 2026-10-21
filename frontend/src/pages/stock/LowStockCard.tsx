import { ArrowRightIcon, CircleCheckIcon } from "lucide-react";
import { Link } from "react-router";

import { useParts } from "@/api/stock";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { StockBadge } from "@/components/StockBadge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";
import { formatNumber } from "@/lib/format";

const SHOWN = 5;

// The few parts closest to running out, for the Home page.
export function LowStockCard() {
  const low = useParts({ status: "low", sort: "quantity", direction: "asc", page: 1 });
  const items = low.data?.items.slice(0, SHOWN) ?? [];

  return (
    <Card className="gap-2 pb-2">
      <CardHeader>
        <CardTitle>{t.stock.lowStockTitle}</CardTitle>
        <CardAction>
          <Button variant="text" size="sm" asChild className="-me-3">
            <Link to="/stock?status=low">
              {t.stock.seeAllLow}
              <ArrowRightIcon aria-hidden="true" className="rtl:rotate-180" />
            </Link>
          </Button>
        </CardAction>
      </CardHeader>
      {low.isError ? (
        <ErrorState onRetry={() => low.refetch()} retrying={low.isFetching} />
      ) : low.isPending ? (
        <div className="grid gap-3 px-6 py-4" aria-busy="true">
          {Array.from({ length: 3 }, (_, index) => (
            <Skeleton key={index} className="h-10 w-full" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <EmptyState icon={CircleCheckIcon} title={t.stock.nothingLow} />
      ) : (
        <ul className="divide-y">
          {items.map((part) => (
            <li key={part.id}>
              <Link
                to={`/stock?part=${part.id}`}
                className="flex items-center justify-between gap-4 px-6 py-3 hover:bg-on-surface/8"
              >
                <span className="grid min-w-0">
                  <span className="truncate text-title-small">{part.name}</span>
                  <span className="text-body-small text-on-surface-variant">{part.sku}</span>
                </span>
                <span className="flex shrink-0 items-center gap-3">
                  {/* "1 / 3" reads left to right in Arabic too, like any fraction. */}
                  <span dir="ltr" className="text-body-medium tabular-nums">
                    {formatNumber(part.quantity)}
                    <span className="text-on-surface-variant"> / {formatNumber(part.min_stock)}</span>
                  </span>
                  <StockBadge status={part.status} />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
