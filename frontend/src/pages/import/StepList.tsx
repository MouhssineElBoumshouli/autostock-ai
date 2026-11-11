import { cn } from "cn";
import { CheckIcon } from "lucide-react";

import { t } from "@/i18n";

export const steps = ["upload", "match", "check", "save"] as const;
export type Step = (typeof steps)[number];

// "1 Upload  2 Match columns  3 Check  4 Save", with the current step in violet.
// On a phone, only the current step's name is shown (the others are just circles), so it
// always fits on one line instead of wrapping.
export function StepList({ current }: { current: Step }) {
  const currentIndex = steps.indexOf(current);

  return (
    <ol className="flex flex-wrap gap-x-3 gap-y-2 sm:gap-x-6">
      {steps.map((step, index) => {
        const done = index < currentIndex;
        const active = index === currentIndex;
        return (
          <li
            key={step}
            aria-current={active ? "step" : undefined}
            className={cn("flex items-center gap-2 text-body-medium", active ? "font-medium text-primary" : "text-on-surface-variant")}
          >
            <span
              className={cn(
                "flex size-6 shrink-0 items-center justify-center rounded-full text-body-small font-medium",
                active && "bg-primary text-on-primary",
                done && "bg-success-container text-on-success-container",
                !active && !done && "bg-surface-container-high",
              )}
            >
              {done ? <CheckIcon aria-hidden="true" className="size-3.5" /> : index + 1}
            </span>
            <span className={cn(!active && "sr-only sm:not-sr-only")}>{t.importFile.steps[step]}</span>
          </li>
        );
      })}
    </ol>
  );
}
