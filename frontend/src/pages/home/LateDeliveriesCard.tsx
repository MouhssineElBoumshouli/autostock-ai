import { TruckIcon } from "lucide-react";

import type { LateDelivery } from "@/api/today";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { t } from "@/i18n";
import { formatDay } from "@/lib/format";

// Purchase orders sent longer ago than the supplier's own delivery time, still not fully received.
export function LateDeliveriesCard({ deliveries }: { deliveries: LateDelivery[] }) {
  return (
    <Card className="gap-3 pb-2">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <TruckIcon aria-hidden="true" className="size-5 text-on-surface-variant" />
          {t.home.lateDeliveries.title}
        </CardTitle>
      </CardHeader>
      {deliveries.length === 0 ? (
        <CardContent>
          <p className="text-body-medium text-on-surface-variant">{t.home.lateDeliveries.empty}</p>
        </CardContent>
      ) : (
        <ul className="divide-y">
          {deliveries.map((delivery) => (
            <li key={delivery.id} className="flex items-center justify-between gap-4 px-6 py-3">
              <span className="grid gap-0.5">
                <span className="text-body-large">
                  <bdi dir="auto">{delivery.order_number}</bdi> · <bdi dir="auto">{delivery.supplier_name}</bdi>
                </span>
                <span className="text-body-small text-on-surface-variant">
                  {t.home.lateDeliveries.sentOn(formatDay(delivery.sent_at.slice(0, 10)))}
                </span>
              </span>
              <span className="shrink-0 text-body-medium text-error">{t.home.lateDeliveries.daysLate(delivery.days_late)}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
