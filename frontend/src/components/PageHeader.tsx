import { cn } from "cn";
import type { ReactNode } from "react";

// Top of every screen: title, one line of explanation, and at most one main button.
export function PageHeader({
  title,
  subtitle,
  action,
  visuallyHideTitle = false,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  // The top app bar already names the page right above this one (see AppShell.tsx): on a page
  // with its own step list right under the title (Import), repeating it reads as a plain
  // duplicate instead of a heading. Kept for screen readers; just not shown again on screen.
  visuallyHideTitle?: boolean;
}) {
  return (
    <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="grid gap-1">
        <h1 className={cn("text-headline-small sm:text-headline-medium", visuallyHideTitle && "sr-only")}>{title}</h1>
        {subtitle && <p className="text-body-medium text-on-surface-variant">{subtitle}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </header>
  );
}
