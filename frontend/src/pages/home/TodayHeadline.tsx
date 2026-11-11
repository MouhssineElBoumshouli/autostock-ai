import { CircleCheckIcon, TriangleAlertIcon } from "lucide-react";
import { cn } from "cn";

import { t } from "@/i18n";

// The one line that answers "what do I need to do today?" at a glance. Never says there is
// nothing to do while parts are out of stock or waiting to be ordered.
export function TodayHeadline({
  outOfStock,
  stockProblems,
  partsToOrder,
  lateDeliveries,
}: {
  outOfStock: number;
  stockProblems: number;
  partsToOrder: number;
  lateDeliveries: number;
}) {
  const ok = outOfStock === 0 && stockProblems === 0 && partsToOrder === 0 && lateDeliveries === 0;
  const Icon = ok ? CircleCheckIcon : TriangleAlertIcon;
  return (
    <div
      className={cn(
        "flex items-center gap-3 rounded-md p-4",
        ok ? "bg-success-container text-on-success-container" : "bg-primary-container text-on-primary-container",
      )}
    >
      <Icon aria-hidden="true" className="size-6 shrink-0" />
      <p className="text-title-large">{t.home.needsYouToday({ outOfStock, stockProblems, partsToOrder, lateDeliveries })}</p>
    </div>
  );
}
