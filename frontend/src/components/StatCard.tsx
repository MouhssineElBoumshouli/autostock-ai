import { cn } from "cn";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

type StatTone = "neutral" | "success" | "warning" | "destructive";

const iconTones: Record<StatTone, string> = {
  neutral: "bg-muted text-foreground",
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-warning",
  destructive: "bg-destructive-soft text-destructive",
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
    <Card className="gap-3 px-5 py-5">
      <div className="flex items-center gap-3">
        <span className={cn("flex size-9 items-center justify-center rounded-lg", iconTones[tone])}>
          <Icon aria-hidden="true" className="size-4.5" />
        </span>
        <span className="text-sm font-medium text-muted-foreground">{label}</span>
      </div>
      {loading ? (
        <div className="grid gap-2 py-1" aria-busy="true">
          <Skeleton className="h-8 w-24" />
          <Skeleton className="h-4 w-36" />
        </div>
      ) : (
        <div className="grid gap-1">
          <p className="text-3xl font-semibold tracking-tight tabular-nums">{value}</p>
          {note && <p className="text-xs text-muted-foreground">{note}</p>}
        </div>
      )}
    </Card>
  );
}
