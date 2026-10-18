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
            className={cn("flex items-center gap-2 text-sm", active ? "font-semibold text-primary" : "text-muted-foreground")}
          >
            <span
              className={cn(
                "flex size-6 items-center justify-center rounded-full text-xs font-semibold",
                active && "bg-primary text-primary-foreground",
                done && "bg-success-soft text-success",
                !active && !done && "bg-muted",
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
