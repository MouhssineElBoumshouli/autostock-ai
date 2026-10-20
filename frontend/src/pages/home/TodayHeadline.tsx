import { CircleCheckIcon, TriangleAlertIcon } from "lucide-react";
import { cn } from "cn";

import { t } from "@/i18n";

// The one line that answers "what do I need to do today?" at a glance.
export function TodayHeadline({ count }: { count: number }) {
  const ok = count === 0;
  const Icon = ok ? CircleCheckIcon : TriangleAlertIcon;
  return (
    <div
      className={cn(
        "flex items-center gap-3 rounded-md p-4",
        ok ? "bg-success-container text-on-success-container" : "bg-primary-container text-on-primary-container",
      )}
    >
      <Icon aria-hidden="true" className="size-6 shrink-0" />
      <p className="text-title-large">{t.home.needsYouToday(count)}</p>
    </div>
  );
}
