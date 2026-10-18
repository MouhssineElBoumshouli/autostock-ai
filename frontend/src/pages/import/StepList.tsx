import { cn } from "cn";
import { CheckIcon } from "lucide-react";

import { t } from "@/i18n";

export const steps = ["upload", "match", "check", "save"] as const;
export type Step = (typeof steps)[number];

// "1 Upload  2 Match columns  3 Check  4 Save", with the current step in violet.
export function StepList({ current }: { current: Step }) {
  const currentIndex = steps.indexOf(current);

  return (
    <ol className="flex flex-wrap gap-x-6 gap-y-2">
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
                "flex size-6 items-center justify-center rounded-full text-body-small font-medium",
                active && "bg-primary text-on-primary",
                done && "bg-success-container text-on-success-container",
                !active && !done && "bg-surface-container-high",
              )}
            >
              {done ? <CheckIcon aria-hidden="true" className="size-3.5" /> : index + 1}
            </span>
            {t.importFile.steps[step]}
          </li>
        );
      })}
    </ol>
  );
}
