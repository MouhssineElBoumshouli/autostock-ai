import { ClipboardListIcon } from "lucide-react";
import { Link } from "react-router";

import type { ToOrderSummary } from "@/api/today";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { t } from "@/i18n";
import { formatMoney, formatNumber } from "@/lib/format";

// How much is waiting to be ordered. Staff see the line count but not the cost.
export function ToOrderCard({
  toOrder,
  canSeeMoney,
  currency,
}: {
  toOrder: ToOrderSummary | null;
  canSeeMoney: boolean;
  currency: string;
}) {
  const hasLines = toOrder !== null && toOrder.lines > 0;
  return (
    <Card className="gap-3 pb-2">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ClipboardListIcon aria-hidden="true" className="size-5 text-on-surface-variant" />
          {t.home.toOrder.title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-body-large">
          {!hasLines
            ? t.home.toOrder.empty
            : canSeeMoney
              ? t.home.toOrder.summary(formatNumber(toOrder.lines), formatMoney(toOrder.total_cost, currency))
              : t.home.toOrder.linesOnly(formatNumber(toOrder.lines))}
        </p>
      </CardContent>
      <CardFooter>
        <Button variant="tonal" size="sm" asChild>
          <Link to="/orders">{t.home.toOrder.button}</Link>
        </Button>
      </CardFooter>
    </Card>
  );
}
