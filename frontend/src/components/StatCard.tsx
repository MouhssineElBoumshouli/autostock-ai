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
// On a phone it is more compact (smaller icon, no note) so the list below shows up sooner.
// When onClick is given, it also acts as a filter toggle: active shows it pressed in.
export function StatCard({
  icon: Icon,
  label,
  value,
  note,
  tone = "neutral",
  loading = false,
  active = false,
  onClick,
}: {
  icon: LucideIcon;
  label: string;
  value: ReactNode;
  note?: string;
  tone?: StatTone;
  loading?: boolean;
  active?: boolean;
  onClick?: () => void;
}) {
  const content = (
    <>
      <div className="flex items-center gap-2 sm:gap-3">
        <span className={cn("flex size-8 shrink-0 items-center justify-center rounded-full sm:size-10", iconTones[tone])}>
          <Icon aria-hidden="true" className="size-4 sm:size-5" />
        </span>
        <span className="truncate text-label-large text-on-surface-variant sm:text-title-small">{label}</span>
      </div>
      {loading ? (
        <div className="grid gap-2 py-1" aria-busy="true">
          <Skeleton className="h-8 w-20 sm:h-10 sm:w-24" />
          <Skeleton className="hidden h-4 w-36 sm:block" />
        </div>
      ) : (
        <div className="grid gap-1">
          <p className="text-headline-small tabular-nums sm:text-display-small">{value}</p>
          {note && <p className="hidden text-body-small text-on-surface-variant sm:block">{note}</p>}
        </div>
      )}
    </>
  );

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        aria-pressed={active}
        className={cn(
          "state-layer flex flex-col gap-3 rounded-md bg-surface-container-low p-4 text-start text-on-surface shadow-elevation-1 sm:gap-4 sm:p-5",
          active && "shadow-[inset_0_0_0_2px_var(--color-primary)]",
        )}
      >
        {content}
      </button>
    );
  }

  return <Card className="gap-3 p-4 sm:gap-4 sm:p-5">{content}</Card>;
}
