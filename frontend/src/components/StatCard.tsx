import { cn } from "cn";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

type StatTone = "neutral" | "success" | "warning" | "error";

const iconTones: Record<StatTone, string> = {
  neutral: "bg-secondary-container text-on-secondary-container",
  success: "bg-success-container text-on-success-container",
  warning: "bg-warning-container text-on-warning-container",
  error: "bg-error-container text-on-error-container",
};

// One key number with its label and a short note, e.g. "Low stock · 682 · 18% of all parts".
export function StatCard({
  icon: Icon,
  label,
  value,
  note,
  tone = "neutral",
  loading = false,
}: {
  icon: LucideIcon;
  label: string;
  value: ReactNode;
  note?: string;
  tone?: StatTone;
  loading?: boolean;
}) {
  return (
    <Card className="gap-4 p-5">
      <div className="flex items-center gap-3">
        <span className={cn("flex size-10 items-center justify-center rounded-full", iconTones[tone])}>
          <Icon aria-hidden="true" className="size-5" />
        </span>
        <span className="text-title-small text-on-surface-variant">{label}</span>
      </div>
      {loading ? (
        <div className="grid gap-2 py-1" aria-busy="true">
          <Skeleton className="h-10 w-24" />
          <Skeleton className="h-4 w-36" />
        </div>
      ) : (
        <div className="grid gap-1">
          <p className="text-display-small tabular-nums">{value}</p>
          {note && <p className="text-body-small text-on-surface-variant">{note}</p>}
        </div>
      )}
    </Card>
  );
}
