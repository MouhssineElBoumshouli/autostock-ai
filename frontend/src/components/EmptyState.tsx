import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

// Shown when there is nothing to list yet. Always offer one helpful next step.
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-4 px-6 py-12 text-center">
      <span className="flex size-14 items-center justify-center rounded-full bg-secondary-container text-on-secondary-container">
        <Icon aria-hidden="true" className="size-6" />
      </span>
      <div className="grid max-w-sm gap-1">
        <p className="text-title-medium">{title}</p>
        {description && <p className="text-body-medium text-on-surface-variant">{description}</p>}
      </div>
      {action}
    </div>
  );
}
